from jinja2 import Environment, FileSystemLoader, exceptions
loader = FileSystemLoader('eacis/templates')
env = Environment(loader=loader)
templates = [
 'base.html',
 'customer/profile_edit.html',
 'customer/profile.html',
 'seller/profile.html'
]
failed = False
for t in templates:
    try:
        env.get_template(t)
        print('TEMPLATE_OK', t)
    except exceptions.TemplateSyntaxError as e:
        print('TEMPLATE_SYNTAX_ERROR', t)
        print(e)
        failed = True
    except Exception as e:
        print('TEMPLATE_OTHER_ERROR', t)
        print(e)
        failed = True
if failed:
    raise SystemExit(2)
else:
    print('ALL_TEMPLATES_OK')
