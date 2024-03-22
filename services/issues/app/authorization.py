from os import getenv
from typing import Any, Dict, List, Optional, Type, TypedDict

from flask import g
from flask_caching import Cache
from sqlalchemy import text
import oso_cloud
from oso_cloud import Oso, Value
from sqlalchemy.orm.session import Session
from sqlalchemy.future import select
from strawberry.types.info import Info

from werkzeug.exceptions import Forbidden, NotFound, Unauthorized

from app.models import Issue

oso = Oso(
    url=getenv("OSO_URL", "https://api.osohq.com"),
    api_key=getenv("OSO_AUTH"),
    data_bindings="facts.yaml",
)
cache = Cache(config={"CACHE_TYPE": "SimpleCache"})


def object_to_oso_value(obj: Any, allow_unbound=False) -> oso_cloud.Value:
    if isinstance(obj, str):
        return {"type": "String", "id": obj}
    elif isinstance(obj, dict):
        assert allow_unbound or ("type" in obj and "id" in obj)
        value: oso_cloud.Value = {}
        if "type" in obj:
            value["type"] = str(obj["type"])
        if "id" in obj:
            value["id"] = str(obj["id"])
        return value
    elif obj is None:
        return {}
    else:
        return {"type": obj.__class__.__name__, "id": str(obj.id)}


def current_user() -> oso_cloud.Value:
    if g.current_user is None:
        raise Unauthorized
    return {"type": "User", "id": str(g.current_user)}


def tell(predicate: str, *args: Any):
    print(f'oso-cloud tell {predicate} {",".join([str(a) for a in args])}')
    return oso.tell({"name": predicate, "args": [object_to_oso_value(a) for a in args]})


BulkFact = TypedDict("BulkFact", {"name": str, "args": list[Any]})


def bulk_update(delete: list[BulkFact] = [], insert: list[BulkFact] = []):
    delete_facts: list[oso_cloud.VariableFact] = [
        {
            "name": fact["name"],
            "args": [object_to_oso_value(a, allow_unbound=True) for a in fact["args"]],
        }
        for fact in delete
    ]
    insert_facts: list[oso_cloud.Fact] = [
        {"name": fact["name"], "args": [object_to_oso_value(a) for a in fact["args"]]}
        for fact in insert
    ]
    return oso.bulk(delete=delete_facts, tell=insert_facts)


def authorize(action: str, resource: Any, parent: Optional[int] = None) -> bool:
    if g.current_user is None:
        raise Unauthorized
    actor = current_user()
    resource = object_to_oso_value(resource)
    try:
        context_facts = []
        if resource["type"] == "Issue":
            context_facts = get_facts_for_issue(parent, resource["id"])
        print(f'oso-cloud authorize {actor} {action} {resource} -c "{context_facts}"')
        res = oso.authorize(actor, action, resource, context_facts)
        print("Allowed" if res else "Denied")
        return res
    except Exception as e:
        print(
            f"error from Oso Cloud: {e} for request: allow({actor}, {action}, {resource})"
        )
        return False


def actions(resource: Any, user: Optional[oso_cloud.Value] = None) -> List[str]:
    if not user and g.current_user is None:
        return []
    actor = current_user()
    resource = object_to_oso_value(resource)
    context_facts = []
    try:
        if resource["type"] == "Issue":
            context_facts = get_facts_for_issue(None, resource["id"])
        print(f'oso-cloud actions {actor} {resource} -c "{context_facts}"')
        res = oso.actions(actor, resource, context_facts=context_facts)
        print(res)
        return sorted(res)
    except Exception as e:
        print(
            f"error from Oso Cloud: {e} for request: allow({actor}, _, {resource}) -c {context_facts}"
        )
        raise e


def list_resources(
    action: str, resource_type: str, parent: Optional[int] = None
) -> List[str]:
    facts = []
    if g.current_user is None:
        return []
    if resource_type == "Issue":
        if not parent:
            raise Exception("cannot get issues without a parent repository")
        facts = get_facts_for_issue(parent, None)

    print(f'oso-cloud list User:{g.current_user} {action} {resource_type} -c "{facts}"')
    return oso.list(
        {"type": "User", "id": g.current_user},
        action,
        resource_type,
        context_facts=facts,
    )


def list_query(action: str, resource_type: str) -> str:
    facts = []
    if g.current_user is None:
        return []
    print(
        f'oso-cloud list_local User:{g.current_user} {action} {resource_type} -c "{facts}"'
    )
    sql = oso.list_local(
        {"type": "User", "id": g.current_user},
        action,
        resource_type,
        column="id::TEXT",
    )
    print(sql)
    return text(sql)


def query(predicate: str, *args: Any):
    print(f'oso-cloud query {predicate} {",".join([str(a) for a in args])}')
    return oso.query(
        {"name": predicate, "args": [object_to_oso_value(a, True) for a in args]}
    )


def get(predicate: str, *args: Any):
    print(f'oso-cloud get {predicate} {",".join([str(a) for a in args])}')
    return oso.get(
        {"name": predicate, "args": [object_to_oso_value(a, True) for a in args]}
    )


def get_or_raise(self, cls: Type[Any], error, **kwargs):
    resource = self.query(cls).filter_by(**kwargs).one_or_none()
    if resource is None:
        raise error
    return resource


def get_or_403(self, cls: Type[Any], **kwargs):
    return self.get_or_raise(cls, Forbidden, **kwargs)


def get_or_404(self, cls: Type[Any], **kwargs):
    return self.get_or_raise(cls, NotFound, **kwargs)


Session.get_or_404 = get_or_404  # type: ignore
Session.get_or_403 = get_or_403  # type: ignore
Session.get_or_raise = get_or_raise  # type: ignore


def get_facts_for_issue(
    repo_id: Optional[int], issue_id: Optional[int]
) -> list[oso_cloud.Fact]:
    if repo_id is None and issue_id is None:
        raise Exception("need to get issues by at least one of repo_id or issue_id")
    query = g.session.query(Issue)
    if repo_id:
        query = query.filter_by(repo_id=repo_id)
    if issue_id:
        query = query.filter_by(id=issue_id)

    issues = query.all()
    facts: list[oso_cloud.Fact] = []

    if repo_id is not None:
        facts.append(
            {
                "name": "in_repo_context",
                "args": [
                    {"type": "Repository", "id": str(repo_id)},
                ],
            }
        )
    else:
        for issue in issues:
            parent: oso_cloud.Value = {"type": "Repository", "id": str(issue.repo_id)}
            resource: oso_cloud.Value = {"type": "Issue", "id": str(issue.id)}

            has_parent: oso_cloud.Fact = {
                "name": "has_relation",
                "args": [resource, "repository", parent],
            }

            creator: oso_cloud.Fact = {
                "name": "has_role",
                "args": [
                    {"type": "User", "id": str(issue.creator_id)},
                    "creator",
                    resource,
                ],
            }

            closed: list[oso_cloud.Fact] = (
                [{"name": "is_closed", "args": [resource]}] if issue.closed else []
            )
            facts.extend([has_parent, creator, *closed])

    return facts


def check_path_authorization(source: Any, info: Info[Any, Any]) -> bool | List[str]:
    import requests

    path = [segment for segment in info.path.as_list() if isinstance(segment, str)]

    from strawberry import relay

    if isinstance(info.return_type, type) and issubclass(
        info.return_type, relay.ListConnection
    ):
        path.append("nodes")
    # for segment in reversed(path):
    #     if isinstance(segment, int):
    #         breakpoint()

    response = requests.get(
        "http://localhost:3001/decisions",
        params={
            "request_id": g.oso_request_id,
            "path": "/" + "/".join(path),
            "parent_id": source.id if hasattr(source, "id") else None,
        },
    )
    if response.status_code != 200:
        print("error from authorization service: ", response.text)
        return True
    result = response.json()
    print(f"check path authorization: {path} -> {result}")
    if "Allowed" in result:
        return result["Allowed"]
    elif "Results" in result:
        return result["Results"]
    else:
        print("unexpected result: ", result)
        return True


import strawberry
from strawberry.schema_directive import Location


@strawberry.federation.schema_directive(
    locations=[Location.FIELD_DEFINITION], compose=True
)
class AuthorizeField:
    action: str
