from flask import render_template, request, redirect, url_for, session, flash, jsonify
from . import admin_bp
from .auth import admin_required
import config_manager

# NOTA DE SEGURIDAD: La contraseña está hardcodeada.
# En un entorno de producción, esto debería gestionarse a través de variables
# de entorno seguras o un sistema de gestión de secretos.
ADMIN_PASSWORD = "super_secret_password_123"

@admin_bp.route('/')
@admin_required
def dashboard():
    """Página principal del panel de administración."""
    return render_template('admin/dashboard.html')

@admin_bp.route('/login', methods=['GET', 'POST'])
def login():
    """Maneja el inicio de sesión del administrador."""
    if request.method == 'POST':
        password = request.form.get('password')
        if password == ADMIN_PASSWORD:
            session['is_admin'] = True
            session.permanent = True # La sesión persistirá entre reinicios del navegador
            flash('Inicio de sesión exitoso.', 'success')
            next_url = request.args.get('next')
            return redirect(next_url or url_for('admin.dashboard'))
        else:
            flash('Contraseña incorrecta.', 'error')

    # Si ya está logueado, redirigir al dashboard
    if session.get('is_admin'):
        return redirect(url_for('admin.dashboard'))

    return render_template('admin/login.html')

@admin_bp.route('/logout')
def logout():
    """Cierra la sesión del administrador."""
    session.pop('is_admin', None)
    flash('Has cerrado la sesión.', 'info')
    return redirect(url_for('admin.login'))

# --- Rutas para la gestión de listas ---

@admin_bp.route('/listas')
@admin_required
def listas():
    """Muestra todas las listas configurables."""
    list_names = config_manager.get_list_names()
    return render_template('admin/listas.html', list_names=list_names)

@admin_bp.route('/listas/<list_name>')
@admin_required
def editar_lista(list_name):
    """Página para editar los elementos de una lista específica."""
    items = config_manager.get_list(list_name)
    return render_template('admin/editar_lista.html', list_name=list_name, items=items)

@admin_bp.route('/api/listas/<list_name>', methods=['POST'])
@admin_required
def api_update_list(list_name):
    """API endpoint para guardar los cambios en una lista."""
    try:
        new_items = request.get_json()
        if new_items is None:
            return jsonify({'success': False, 'message': 'No se recibieron datos válidos.'}), 400

        if config_manager.save_list(list_name, new_items):
            return jsonify({'success': True, 'message': f'Lista "{list_name}" actualizada exitosamente.'})
        else:
            return jsonify({'success': False, 'message': 'Error al guardar la lista.'}), 500
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error del servidor: {str(e)}'}), 500
