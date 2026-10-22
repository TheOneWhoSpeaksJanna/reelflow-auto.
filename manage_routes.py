from flask import Blueprint, jsonify
manage_api = Blueprint('manage_api', __name__, url_prefix='/api')

@manage_api.get('/config')
def config():
    return jsonify(ok=True)
