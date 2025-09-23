from functools import wraps
from flask import Blueprint, render_template, request, redirect, url_for, session, flash
import config_manager

# Definir el Blueprint para el panel de administración
admin_bp = Blueprint(
    'admin',
    __name__,
    template_folder='templates',
    url_prefix='/admin'
)

# --- Decorador de autenticación ---
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'admin_logged_in' not in session:
            flash('Por favor, inicie sesión para acceder a esta página.', 'warning')
            return redirect(url_for('admin.login'))
        return f(*args, **kwargs)
    return decorated_function

# --- Rutas de autenticación ---
@admin_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        # En una aplicación real, verificaría un usuario y contraseña hasheados
        # Aquí, usaremos una verificación simple por simplicidad
        password = request.form.get('password')
        if password == 'AdminUIB': # Contraseña simple para el ejercicio
            session['admin_logged_in'] = True
            flash('Inicio de sesión exitoso.', 'success')
            return redirect(url_for('admin.dashboard'))
        else:
            flash('Contraseña incorrecta.', 'danger')
    return render_template('admin/login.html')

@admin_bp.route('/logout')
@admin_required
def logout():
    session.pop('admin_logged_in', None)
    flash('Ha cerrado sesión.', 'info')
    return redirect(url_for('admin.login'))

# --- Rutas del panel de administración ---
@admin_bp.route('/')
@admin_required
def dashboard():
    return render_template('admin/dashboard.html')

@admin_bp.route('/listas')
@admin_required
def listas():
    list_names = config_manager.get_all_list_names()
    return render_template('admin/listas.html', list_names=list_names)

@admin_bp.route('/listas/editar/<list_name>', methods=['GET'])
@admin_required
def editar_lista(list_name):
    items = config_manager.get_list(list_name)
    if items is None:
        flash(f"La lista '{list_name}' no fue encontrada.", 'danger')
        return redirect(url_for('admin.listas'))

    # Determinar si es una lista de objetos (vendedores) o strings
    is_object_list = isinstance(items[0], dict) if items else False

    return render_template('admin/editar_lista.html', list_name=list_name, items=items, is_object_list=is_object_list)

@admin_bp.route('/listas/guardar/<list_name>', methods=['POST'])
@admin_required
def guardar_lista(list_name):
    # Lógica para manejar tanto listas simples como listas de objetos
    is_object_list = 'is_object_list' in request.form

    if is_object_list:
        # Manejar lista de objetos (vendedores)
        items = []
        nombres = request.form.getlist('item_nombre')
        comisiones = request.form.getlist('item_comision')
        for nombre, comision in zip(nombres, comisiones):
            if nombre: # Solo agregar si el nombre no está vacío
                items.append({'nombre': nombre, 'comision': comision or '0'})
    else:
        # Manejar lista simple de strings
        items_str = request.form.get('items')
        items = [item.strip() for item in items_str.split('\n') if item.strip()]

    if config_manager.save_list(list_name, items):
        flash(f"Lista '{list_name}' guardada con éxito.", 'success')
    else:
        flash(f"Error al guardar la lista '{list_name}'.", 'danger')

    return redirect(url_for('admin.editar_lista', list_name=list_name))
