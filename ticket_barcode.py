# import EAN13 from barcode module
import barcode

# import ImageWriter to generate an image file
from barcode.writer import ImageWriter

# Make sure to pass the number as string
number = "https://ucsc.service-now.com/sc_req_item.do?sysparm_query=number=RITM0091694"

# Now, let's create an object of EAN13 class and
# pass the number with the ImageWriter() as the
# writer
# my_code = EAN13(number, writer=ImageWriter())

# # Our barcode is ready. Let's save it.
# my_code.save("new_code1")


def generate_barcode(data, barcode_format, options=None):
    # Get the barcode class corresponding to the specified format
    barcode_class = barcode.get_barcode_class(barcode_format)
    # Create a barcode image using the provided data and format
    barcode_image = barcode_class(data, writer=ImageWriter())
    # Save the barcode image to a file named "barcode" with the specified options
    barcode_image.save("barcode", options=options)


generate_barcode(number, "code128")
