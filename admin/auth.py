from functools import wraps
from flask import session, redirect, url_for, request

def admin_required(f):
    """
    Decorador para restringir el acceso a rutas solo a administradores.
    Verifica si la clave 'is_admin' está en la sesión. Si no, redirige
    a la página de login.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('is_admin'):
            # Almacena la URL a la que el usuario intentaba acceder para redirigirlo después del login.
            return redirect(url_for('admin.login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function
