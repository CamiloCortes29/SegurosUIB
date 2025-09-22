from flask import Blueprint

# Define el Blueprint para el módulo de administración.
# - 'admin': nombre del blueprint.
# - __name__: el nombre del paquete del blueprint, ayuda a Flask a localizar plantillas y archivos estáticos.
# - template_folder: especifica que las plantillas para este blueprint están en un subdirectorio 'templates'.
# - url_prefix: todas las rutas definidas en este blueprint comenzarán con /admin.
admin_bp = Blueprint('admin', __name__, template_folder='templates', url_prefix='/admin')

# Importar las rutas al final para evitar importaciones circulares.
# Las rutas usarán el objeto 'admin_bp' que acabamos de crear.
from . import routes, auth
