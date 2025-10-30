"""Extract footprint code and modify it in a KiCad .kicad_pcb file.

This script can extract the complete footprint code for a specified reference,
or modify the footprint by adding/removing (hide yes) to/from the model field,
or offset the 3D model coordinates.

Usage:
    Extract:
        python kicad_footprint_manager.py <file> <rf> --code
    Hide 3D model (all models):
        python kicad_footprint_manager.py <file> <rf> --hide
    Hide specific 3D model by index:
        python kicad_footprint_manager.py <file> <reference> --hide
        --idx N
    Show 3D model (all models):
        python kicad_footprint_manager.py <file> <reference> --show
    Show specific 3D model by index:
        python kicad_footprint_manager.py <file> <reference> --show
        --idx N
    Offset coordinates (all models):
        python kicad_footprint_manager.py <file> <reference>
        --offset X Y Z
    Offset specific model by index:
        python kicad_footprint_manager.py <file> <reference>
        --offset X Y Z --idx N
    Set position (all models):
        python kicad_footprint_manager.py <file> <reference>
        --position X Y Z
    Set position for specific model by index:
        python kicad_footprint_manager.py <file> <reference>
        --position X Y Z --idx N

"""

import argparse
import re
import sys
from pathlib import Path
from typing import Dict, Tuple, Union


def parse_kicad_pcb(
    file_path: Union[str, Path],
) -> Tuple[str, Dict[str, Dict[str, Union[str, int]]]]:
    """Parse a KiCad PCB file and extract footprint data by reference.

    Args:
        file_path: Path to the .kicad_pcb file

    Returns:
        A tuple containing the file content and a dict mapping reference
        designators to footprint data, including the start and end positions
        in the file

    """
    with open(file_path, "r", encoding="utf-8") as file:
        content = file.read()

    footprints = {}

    for match in re.finditer(r"\(footprint", content):
        start_pos = match.start()

        paren_count = 0
        for i in range(start_pos, len(content)):
            if content[i] == "(":
                paren_count += 1
            elif content[i] == ")":
                paren_count -= 1
                if paren_count == 0:
                    footprint_raw = content[start_pos : i + 1]

                    ref_match = re.search(
                        r'\(property "Reference"\s+"([^\"]+)"', footprint_raw
                    )
                    if ref_match:
                        ref = ref_match.group(1)
                        footprints[ref] = {
                            "full_data": footprint_raw,
                            "start_pos": start_pos,
                            "end_pos": i + 1,
                        }
                    break

    return content, footprints


def replace_footprint_in_file(
    file_path: Union[str, Path], reference: str, new_footprint_code: str
) -> bool:
    """Replace the footprint with the specified reference in the file.

    Args:
        file_path: Path to the .kicad_pcb file
        reference: Reference designator to replace
        new_footprint_code: New footprint code to insert

    Returns:
        True if replacement was successful, False otherwise

    """
    content, footprints = parse_kicad_pcb(file_path)

    if reference not in footprints:
        print(f"Error: No footprint found with reference: {reference}")
        return False

    footprint_info = footprints[reference]
    start_pos = footprint_info["start_pos"]
    end_pos = footprint_info["end_pos"]

    new_content = content[:start_pos] + new_footprint_code + content[end_pos:]

    with open(file_path, "w", encoding="utf-8") as file:
        file.write(new_content)

    print(f"Successfully replaced footprint for reference {reference}")
    return True


def add_hide_to_model(footprint_code: str) -> str:
    """Add (hide yes) to the model field in the footprint code.

    Args:
        footprint_code: The footprint code to modify

    Returns:
        The modified footprint code

    """
    pattern = r'(\(model\s+"[^"]+"\s*\n\s*)(\(\s*offset)'

    def replace_func(match: re.Match) -> str:
        return match.group(1) + "(hide yes)\n\t\t\t" + match.group(2)

    modified_code = re.sub(pattern, replace_func, footprint_code)

    hide_pattern = r'\(model\s+"[^"]+"\s*\n\s*\t*\s*\(\s*hide\s+yes\s*\)'
    if re.search(hide_pattern, footprint_code):
        print(
            "Warning: This footprint already has "
            "(hide yes) in the model section."
        )

    return modified_code


def remove_hide_from_model(footprint_code: str) -> str:
    """Remove (hide yes) from the model field in the footprint code.

    Args:
        footprint_code: The footprint code to modify

    Returns:
        The modified footprint code

    """
    pattern = (
        r'(\(model\s+"[^"]+"\s*\n\s*)'
        r"(\t*\s*\(\s*hide\s+yes\s*\)\s*\n\s*)"
        r"(\(\s*offset)"
    )

    def replace_func(match: re.Match) -> str:
        return match.group(1) + match.group(3)

    modified_code = re.sub(pattern, replace_func, footprint_code)

    hide_pattern = r'\(model\s+"[^"]+"\s*\n\s*\t*\s*\(\s*hide\s+yes\s*\)'
    if not re.search(hide_pattern, footprint_code):
        print(
            "Note: This footprint does not have "
            "(hide yes) in the model section."
        )

    return modified_code


def offset_model_coordinates(
    footprint_code: str, dx: float, dy: float, dz: float
) -> str:
    """Offset the existing model coordinates by the specified deltas.

    Args:
        footprint_code: The footprint code to modify
        dx: Offset to add to X coordinate
        dy: Offset to add to Y coordinate
        dz: Offset to add to Z coordinate

    Returns:
        The modified footprint code

    """
    pattern = (
        r'(\(model\s+"[^"]+"\s*\n\s*(?:\(hide yes\)\s*\n\s*)?'
        r"\(offset\s*\n\s*\(xyz\s+)"
        r"([+-]?\d+\.?\d*)\s+"
        r"([+-]?\d+\.?\d*)\s+"
        r"([+-]?\d+\.?\d*)"
        r"(\s*\))"
    )

    def replace_func(match: re.Match) -> str:
        x = float(match.group(2)) + dx
        y = float(match.group(3)) + dy
        z = float(match.group(4)) + dz
        return f"{match.group(1)}{x} {y} {z}{match.group(5)}"

    modified_code = re.sub(pattern, replace_func, footprint_code)

    if modified_code == footprint_code:
        print("Warning: No offset section found in the model.")
    else:
        print(f"Applied offset: ({dx:+g}, {dy:+g}, {dz:+g})")

    return modified_code


def set_model_position(
    footprint_code: str, x: float, y: float, z: float
) -> str:
    """Set the model coordinates to the specified values.

    Args:
        footprint_code: The footprint code to modify
        x: X coordinate to set
        y: Y coordinate to set
        z: Z coordinate to set

    Returns:
        The modified footprint code

    """
    pattern = (
        r'(\(model\s+"[^"]+"\s*\n\s*(?:\(hide yes\)\s*\n\s*)?'
        r"\(offset\s*\n\s*\(xyz\s+)"
        r"([+-]?\d+\.?\d*)\s+"
        r"([+-]?\d+\.?\d*)\s+"
        r"([+-]?\d+\.?\d*)"
        r"(\s*\))"
    )

    def replace_func(match: re.Match) -> str:
        return f"{match.group(1)}{x} {y} {z}{match.group(5)}"

    modified_code = re.sub(pattern, replace_func, footprint_code)

    if modified_code == footprint_code:
        print("Warning: No offset section found in the model.")
    else:
        print(f"Set position: ({x}, {y}, {z})")

    return modified_code


def modify_specific_model_by_index(
    footprint_code: str,
    model_index: int,
    operation: str,
    **kwargs: Tuple[float, float, float],
) -> str:
    """Modify a specific model by index.

    Args:
        footprint_code: The footprint code to modify
        model_index: Index of the specific model to modify (0-based)
        operation: Type of operation ("hide", "show", "offset", "position")
        **kwargs: Additional arguments for specific operations

    Returns:
        The modified footprint code

    """
    # Find all models in the footprint by parsing them properly
    models = []
    start = 0

    # Find each model section by counting parentheses
    while True:
        model_start_match = re.search(
            r'\(model\s+"[^"]+"', footprint_code[start:]
        )
        if not model_start_match:
            break

        actual_start = start + model_start_match.start()

        # Count parentheses to find the end of this model section
        paren_count = 0
        for i in range(actual_start, len(footprint_code)):
            if footprint_code[i] == "(":
                paren_count += 1
            elif footprint_code[i] == ")":
                paren_count -= 1
                if paren_count == 0:
                    model_end = i + 1
                    model_content = footprint_code[actual_start:model_end]
                    models.append((actual_start, model_end, model_content))
                    break

        start = model_end
        if start >= len(footprint_code):
            break

    if not models:
        print("No 3D models found in this footprint.")
        return footprint_code

    # Check if the requested index is valid
    if model_index < 0 or model_index >= len(models):
        print(
            f"Model index {model_index} is out of range "
            f"(0-{len(models) - 1})."
        )
        return footprint_code

    model_start, model_end, model_content = models[model_index]
    modified_code = footprint_code

    # Apply the appropriate operation
    if operation == "hide":
        if "(hide yes)" not in model_content:
            # Add (hide yes) after the model path line
            updated_model = re.sub(
                r'(\(model\s+"[^"]+"\s*\n\s*)',
                r"\1(hide yes)\n\t\t\t",
                model_content,
                count=1,
            )
            modified_code = (
                modified_code[:model_start]
                + updated_model
                + modified_code[model_end:]
            )
            print(f"Added (hide yes) to model at index {model_index}")
        else:
            print(f"Model at index {model_index} already has (hide yes)")
    elif operation == "show":
        if "(hide yes)" in model_content:
            # Remove (hide yes) from this model
            updated_model = re.sub(
                r"\(\s*hide\s+yes\s*\)\s*\n\s*", "", model_content, count=1
            )
            # Clean up extra newlines
            updated_model = updated_model.replace("\n\t\t\t\n", "\n\t\t\t")
            modified_code = (
                modified_code[:model_start]
                + updated_model
                + modified_code[model_end:]
            )
            print(f"Removed (hide yes) from model at index {model_index}")
        else:
            print(f"Model at index {model_index} does not have (hide yes)")
    elif operation == "offset":
        dx, dy, dz = kwargs.get("offset_values", (0, 0, 0))
        # Update the xyz coordinates
        updated_model = re.sub(
            r"(\(\s*offset\s*\n\s*\(\s*xyz\s+)"
            r"([+-]?\d+\.?\d*)\s+([+-]?\d+\.?\d*)\s+"
            r"([+-]?\d+\.?\d*)(\s*\)\s*\))",
            lambda m: (
                f"{m.group(1)}{float(m.group(2)) + dx} "
                f"{float(m.group(3)) + dy} {float(m.group(4)) + dz}"
                f"{m.group(5)}"
            ),
            model_content,
        )
        if updated_model != model_content:
            modified_code = (
                modified_code[:model_start]
                + updated_model
                + modified_code[model_end:]
            )
            print(
                f"Applied offset to model at index "
                f"{model_index}: ({dx:+g}, {dy:+g}, {dz:+g})"
            )
        else:
            print(
                f"Could not apply offset to model at index {model_index}, "
                "no coordinates found"
            )
    elif operation == "position":
        x, y, z = kwargs.get("position_values", (0, 0, 0))
        # Set the xyz coordinates
        updated_model = re.sub(
            r"(\(\s*offset\s*\n\s*\(\s*xyz\s+)"
            r"([+-]?\d+\.?\d*)\s+([+-]?\d+\.?\d*)\s+"
            r"([+-]?\d+\.?\d*)(\s*\)\s*\))",
            lambda m: f"{m.group(1)}{x} {y} {z}{m.group(5)}",
            model_content,
        )
        if updated_model != model_content:
            modified_code = (
                modified_code[:model_start]
                + updated_model
                + modified_code[model_end:]
            )
            print(
                f"Set position for model at index "
                f"{model_index}: ({x}, {y}, {z})"
            )
        else:
            print(
                f"Could not set position for model at index {model_index}, "
                "no coordinates found"
            )

    return modified_code


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description=(
            "Extract footprint code and modify 3D model visibility "
            "in a KiCad .kicad_pcb file"
        )
    )
    parser.add_argument("pcb_file", help="Path to the .kicad_pcb file")
    parser.add_argument(
        "reference",
        help="Reference designator to extract/modify (e.g., M3, U2)",
    )
    parser.add_argument(
        "--code",
        action="store_true",
        help="Show the complete footprint code for a specific footprint",
    )
    parser.add_argument(
        "--hide",
        action="store_true",
        help="Add (hide yes) to the model section of the footprint",
    )
    parser.add_argument(
        "--show",
        action="store_true",
        help=(
            "Remove (hide yes) from the model section "
            "of the footprint to show 3D model"
        ),
    )
    parser.add_argument(
        "--offset",
        nargs=3,
        type=float,
        metavar=("DX", "DY", "DZ"),
        help="Offset the model coordinates by (dx, dy, dz)",
    )
    parser.add_argument(
        "--position",
        nargs=3,
        type=float,
        metavar=("X", "Y", "Z"),
        help="Set the model coordinates to (x, y, z)",
    )
    parser.add_argument(
        "--idx",
        type=int,
        help="Index of the specific model to modify "
        "(0-based, applies to --hide, --show, --offset, --position)",
    )

    args = parser.parse_args()

    pcb_path = Path(args.pcb_file)

    if not pcb_path.exists():
        print(f"Error: File {pcb_path} does not exist.")
        sys.exit(1)

    if not pcb_path.suffix.lower() == ".kicad_pcb":
        print(f"Warning: File {pcb_path} does not have .kicad_pcb extension.")

    if (
        args.code
        and args.reference
        and not any([args.hide, args.show, args.offset])
    ):
        _, footprints = parse_kicad_pcb(pcb_path)
        if args.reference in footprints:
            print(f"Complete footprint code for reference: {args.reference}")
            print(footprints[args.reference]["full_data"])
        else:
            print(f"No footprint found with reference: {args.reference}")
            print("Available references:")
            for ref in sorted(footprints.keys()):
                print(f"  - {ref}")
    elif (
        args.hide
        and args.reference
        and not any([args.code, args.show, args.offset])
    ):
        _, footprints = parse_kicad_pcb(pcb_path)
        if args.reference not in footprints:
            print(
                f"Error: No footprint found with reference: {args.reference}"
            )
            sys.exit(1)

        original_footprint = footprints[args.reference]["full_data"]
        if args.idx is not None:
            modified_footprint = modify_specific_model_by_index(
                original_footprint, args.idx, "hide"
            )
        else:
            modified_footprint = add_hide_to_model(original_footprint)

        replace_footprint_in_file(
            pcb_path, args.reference, modified_footprint
        )
    elif (
        args.show
        and args.reference
        and not any([args.code, args.hide, args.offset])
    ):
        _, footprints = parse_kicad_pcb(pcb_path)
        if args.reference not in footprints:
            print(
                f"Error: No footprint found with reference: {args.reference}"
            )
            sys.exit(1)

        original_footprint = footprints[args.reference]["full_data"]
        if args.idx is not None:
            modified_footprint = modify_specific_model_by_index(
                original_footprint, args.idx, "show"
            )
        else:
            modified_footprint = remove_hide_from_model(original_footprint)

        replace_footprint_in_file(
            pcb_path, args.reference, modified_footprint
        )
    elif (
        args.offset
        and args.reference
        and not any([args.code, args.hide, args.show, args.position])
    ):
        _, footprints = parse_kicad_pcb(pcb_path)
        if args.reference not in footprints:
            print(
                f"Error: No footprint found with reference: {args.reference}"
            )
            sys.exit(1)

        original_footprint = footprints[args.reference]["full_data"]
        if args.idx is not None:
            modified_footprint = modify_specific_model_by_index(
                original_footprint,
                args.idx,
                "offset",
                offset_values=(
                    args.offset[0],
                    args.offset[1],
                    args.offset[2],
                ),
            )
        else:
            modified_footprint = offset_model_coordinates(
                original_footprint,
                args.offset[0],
                args.offset[1],
                args.offset[2],
            )

        replace_footprint_in_file(
            pcb_path, args.reference, modified_footprint
        )
    elif (
        args.position
        and args.reference
        and not any([args.code, args.hide, args.show, args.offset])
    ):
        _, footprints = parse_kicad_pcb(pcb_path)
        if args.reference not in footprints:
            print(
                f"Error: No footprint found with reference: {args.reference}"
            )
            sys.exit(1)

        original_footprint = footprints[args.reference]["full_data"]
        if args.idx is not None:
            modified_footprint = modify_specific_model_by_index(
                original_footprint,
                args.idx,
                "position",
                position_values=(
                    args.position[0],
                    args.position[1],
                    args.position[2],
                ),
            )
        else:
            modified_footprint = set_model_position(
                original_footprint,
                args.position[0],
                args.position[1],
                args.position[2],
            )

        replace_footprint_in_file(
            pcb_path, args.reference, modified_footprint
        )
    else:
        _, footprints = parse_kicad_pcb(pcb_path)
        print(f"Found {len(footprints)} footprints in {pcb_path.name}:")
        print("Available references:")
        for ref in sorted(footprints.keys()):
            print(f"  - {ref}")
        print("\nUsage:")
        print("  Extract: --code option")
        print("  Hide 3D model: --hide option")
        print("  Show 3D model: --show option")
        print("  Offset coordinates: --offset DX DY DZ option")
        print("  Set position: --position X Y Z option")
        print("  Target specific model by index: --idx N (0-based)")
