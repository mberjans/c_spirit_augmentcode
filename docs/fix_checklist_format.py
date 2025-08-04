import re

def fix_checkbox_format(input_file, output_file):
    """
    Fix the checkbox format in the input file and write the corrected content to the output file.
    Correct format: "- [ ]"
    """
    try:
        with open(input_file, 'r') as infile:
            lines = infile.readlines()

        corrected_lines = []
        for line in lines:
            # Replace incorrect checkbox formats with the correct format
            corrected_line = re.sub(
                r'^\s*[\*\-]\s*\[ \]|^\s*\*\s*\[ \]|^\s*\*\s*\\\[ \\\]',
                '- [ ]',
                line
            )
            corrected_lines.append(corrected_line)

        with open(output_file, 'w') as outfile:
            outfile.writelines(corrected_lines)

        print(f"Checkbox format fixed and written to {output_file}")

    except FileNotFoundError:
        print(f"File {input_file} not found.")
    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    input_file = "checklist.md"
    output_file = "new_checklist.md"
    fix_checkbox_format(input_file, output_file)
