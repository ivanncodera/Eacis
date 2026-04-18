from jinja2 import Environment, FileSystemLoader, exceptions
import sys

loader = FileSystemLoader('eacis/templates')
env = Environment(loader=loader)
try:
    env.get_template('customer/order_detail.html')
    print('TEMPLATE_COMPILE_OK')
except exceptions.TemplateSyntaxError as e:
    print('TEMPLATE_SYNTAX_ERROR')
    print(e)
    sys.exit(2)
except Exception as e:
    print('TEMPLATE_OTHER_ERROR')
    print(e)
    sys.exit(3)
