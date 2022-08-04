from flask import Blueprint, g, request, current_app, jsonify, session as flask_session
from werkzeug.exceptions import BadRequest, NotFound

from ..models import User

from os import getenv
from oso_cloud import Oso

bp = Blueprint("routes.session", __name__, url_prefix="/session")


@bp.route("", methods=["GET"])
def show():
    return jsonify(g.current_user.repr() if g.current_user else None)


@bp.route("", methods=["POST"])
def create():
    payload = request.get_json(force=True)
    if "id" not in payload:
        raise BadRequest
    user = g.session.query(User).filter_by(id=payload["id"]).one_or_none()
    if user is None:
        flask_session.pop("current_user_id", None)
        raise NotFound
    flask_session["current_user_id"] = user.id
    result = user.repr()
    result["token"] = Oso.mint_actor_token(getenv("OSO_ACTOR_ROOT"), user.repr())
    return result, 201


@bp.route("", methods=["DELETE"])
def delete():
    flask_session.pop("current_user_id", None)
    return current_app.response_class(status=204, mimetype="application/json")
