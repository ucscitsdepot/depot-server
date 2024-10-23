from brother_ql.conversion import convert
from brother_ql.backends.helpers import send
from brother_ql.raster import BrotherQLRaster

model = "QL-570"
printer = "file:///dev/usb/lp0"
backend = "linux_kernel"
images = ["static/depot.png"]
label = "62"

qlr = BrotherQLRaster(model)
qlr.exception_on_warning = True

instructions = convert(qlr=qlr, images=images, label=label)
send(instructions=instructions, printer_identifier=printer, backend_identifier=backend, blocking=True)