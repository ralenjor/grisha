import sys

def quote_lines(input_file, output_file):
	try:
		with open(input_file, 'r') as infile, open(output_file, 'w') as outfile:
			for line in infile:
			# .strip() removes existing newline characters and extra whitespace
				clean_line  = line.strip()

			#only process lines that aren't empty
				if clean_line:
					outfile.write(f'"{clean_line}",\n')

		print(f"Success. Quoted text saved to {output_file}")



	except Exception as e:
		print(f"An unexpected error occurred: {e}")

if __name__ == "__main__":
	 quote_lines('data.txt', 'quoted_data.txt')
	# sys.argv[0] is script name
	# sys.argv[1] is input file
	# sys.argv[2] is output file

if len(sys.argv) != 3:
       	print("Usage: python addquotes.py <input_file> <output_file>")
else:
        quote_lines(sys.argv[1], sys.argv[2])
