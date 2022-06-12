#
# sonar-tools
# Copyright (C) 2019-2022 Olivier Korach
# mailto:olivier.korach AT gmail DOT com
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 3 of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this program; if not, write to the Free Software Foundation,
# Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.
#
"""

    Abstraction of the SonarQube "quality gate" concept

"""

import json
import sonar.sqobject as sq
from sonar import permissions, options, measures
import sonar.utilities as util

from sonar.audit import rules, severities, types
import sonar.audit.problem as pb


_QUALITY_GATES = {}
_MAP = {}

_CREATE_API = "qualitygates/create"
_SEARCH_API = "qualitygates/list"
_DETAILS_API = "qualitygates/show"

NEW_ISSUES_SHOULD_BE_ZERO = "Any numeric threshold on new issues should be 0 or should be removed from QG conditions"

GOOD_QG_CONDITIONS = {
    "new_reliability_rating": (1, 1, "Any rating other than A would let bugs slip through in new code"),
    "new_security_rating": (1, 1, "Any rating other than A would let vulnerabilities slip through in new code"),
    "new_maintainability_rating": (1, 1, "Expectation is that code smells density on new code is low enough to get A rating"),
    "new_coverage": (20, 90, "Coverage below 20% is a too low bar, above 90% is overkill"),
    "new_bugs": (0, 0, NEW_ISSUES_SHOULD_BE_ZERO),
    "new_vulnerabilities": (0, 0, NEW_ISSUES_SHOULD_BE_ZERO),
    "new_security_hotspots": (0, 0, NEW_ISSUES_SHOULD_BE_ZERO),
    "new_blocker_violations": (0, 0, NEW_ISSUES_SHOULD_BE_ZERO),
    "new_critical_violations": (0, 0, NEW_ISSUES_SHOULD_BE_ZERO),
    "new_major_violations": (0, 0, NEW_ISSUES_SHOULD_BE_ZERO),
    "new_duplicated_lines_density": (1, 5, "Duplication on new code of less than 1% is overkill, more than 5% is too relaxed"),
    "new_security_hotspots_reviewed": (100, 100, "All hotspots on new code must be reviewed, any other condition than 100% make little sense"),
    "reliability_rating": (4, 4, "Threshold on overall code should not be too strict or passing the QG will be often impossible"),
    "security_rating": (4, 4, "Threshold on overall code should not be too strict or passing the QG will be often impossible"),
}


class QualityGate(sq.SqObject):
    def __init__(self, name, endpoint, data=None, create_data=None):
        super().__init__(name, endpoint)
        self.name = name
        self.is_built_in = False
        self._conditions = None
        self._permissions = None
        self._projects = None
        self.is_default = False
        if create_data is not None:
            self.post(_CREATE_API, params={"name": name})
            self.set_conditions(create_data.get("conditions", None))
            self.set_permissions(create_data.get("permissions", None))
            data = search_by_name(endpoint, name)
        elif data is None:
            data = search_by_name(endpoint, name)
        self.key = data["id"]
        self.name = data["name"]
        self.is_default = data.get("isDefault", False)
        self.is_built_in = data.get("isBuiltIn", False)
        self.conditions()
        self.permissions()
        _QUALITY_GATES[_uuid(self.name, self.key)] = self
        _MAP[self.name] = self.key

    def __str__(self):
        return f"quality gate '{self.name}'"

    def projects(self):
        if self._projects is not None:
            return self._projects
        params = {"ps": 500}
        page, nb_pages = 1, 1
        self._projects = {}
        while page <= nb_pages:
            params["p"] = page
            resp = self.get("qualitygates/search", params=params, exit_on_error=False)
            if resp.status_code // 100 == 2:
                data = json.loads(resp.text)
                for prj in data:
                    if "key" in prj:
                        self._projects[prj["key"]] = prj
                    else:
                        self._projects[prj["id"]] = prj
                nb_pages = util.nbr_pages(data)
            elif resp.status_code not in (400, 404):
                # For no projects, 8.9 returns 404, 9.x returns 400
                util.exit_fatal(
                    f"alm_settings/get_binding returning status code {resp.status_code}, exiting",
                    options.ERR_SONAR_API,
                )
            page += 1
        return self._projects

    def count_projects(self):
        return len(self.projects())

    def conditions(self, encoded=False):
        if self._conditions is None:
            self._conditions = []
            data = json.loads(self.get(_DETAILS_API, params={"name": self.name}).text)
            for c in data.get("conditions", []):
                self._conditions.append(c)
        if encoded:
            return _encode_conditions(self._conditions)
        return self._conditions

    def clear_conditions(self):
        if self.is_built_in:
            util.logger.warning("Can't clear conditions of built-in %s", str(self))
        else:
            util.logger.debug("Clearing conditions of %s", str(self))
            for c in self.conditions():
                self.post("qualitygates/delete_condition", params={"id": c["id"]})
            self._conditions = None

    def set_conditions(self, conditions_list):
        if conditions_list is None or len(conditions_list) == 0:
            return
        if self.is_built_in:
            util.logger.warning("Can't set conditions of built-in %s", str(self))
            return
        self.clear_conditions()
        util.logger.debug("Setting conditions of %s", str(self))
        params = {"gateName": self.name}
        for cond in conditions_list:
            (params["metric"], params["op"], params["error"]) = _decode_condition(cond)
            self.post("qualitygates/create_condition", params=params)
        self.conditions()

    def permissions(self):
        if self.endpoint.version() < (9, 2, 0):
            return None
        if self._permissions is not None:
            return self._permissions
        self._permissions = {}
        perms = util.remove_nones(permissions.get_qg(self.endpoint, self.name, "users", "login"))
        if perms is not None:
            self._permissions["users"] = perms
        perms = util.remove_nones(permissions.get_qg(self.endpoint, self.name, "groups", "name"))
        if perms is not None:
            self._permissions["groups"] = perms
        return self._permissions

    def clear_permissions(self):
        if self.is_built_in:
            util.logger.warning("Can't clear permissions of built-in %s", str(self))
        else:
            util.logger.debug("Clearing permissions of %s", str(self))
            perms = self.permissions()
            if "users" in perms:
                for u in util.csv_to_list(perms["users"]):
                    self.post("qualitygates/remove_user", params={"gateName": self.name, "login": u})
            if "groups" in perms:
                for g in util.csv_to_list(perms["groups"]):
                    self.post("qualitygates/remove_group", params={"gateName": self.name, "groupName": g})
            self._permissions = None

    def set_permissions(self, permissions_list):
        util.logger.debug("Setting permissions of %s with %s", str(self), str(permissions_list))
        if permissions_list is None or len(permissions_list) == 0:
            return
        if self.is_built_in:
            util.logger.warning("Can't set permissions of built-in %s", str(self))
            return
        self.clear_permissions()
        if "groups" in permissions_list:
            pl = permissions_list["groups"]
            if isinstance(pl, str):
                pl = util.csv_to_list(pl)
            for p in pl:
                self.post("qualitygates/add_group", params={"gateName": self.name, "groupName": p})
        if "users" in permissions_list:
            pl = permissions_list["users"]
            if isinstance(pl, str):
                pl = util.csv_to_list(pl)
            for p in pl:
                self.post("qualitygates/add_user", params={"gateName": self.name, "login": p})
        self.permissions()

    def update(self, **data):
        if "name" in data and data["name"] != self.name:
            util.logger.info("Renaming %s with %s", str(self), data["name"])
            self.post("qualitygates/rename", params={"id": self.key, "name": data["name"]})
            _MAP.pop(_uuid(self.name, self.key), None)
            self.name = data["name"]
            _MAP[_uuid(self.name, self.key)] = self
        self.set_conditions(data.get("conditions", []))
        self.set_permissions(data.get("permissions", []))
        return self

    def __audit_conditions__(self):
        problems = []
        for c in self.conditions():
            m = c["metric"]
            if m not in GOOD_QG_CONDITIONS:
                rule = rules.get_rule(rules.RuleId.QG_WRONG_METRIC)
                msg = rule.msg.format(str(self), m)
                problems.append(pb.Problem(rule.type, rule.severity, msg))
                continue
            val = int(c["error"])
            (mini, maxi, msg) = GOOD_QG_CONDITIONS[m]
            util.logger.debug("Condition on metric '%s': Check that %d in range [%d - %d]", m, val, mini, maxi)
            if val < mini or val > maxi:
                msg = f"{str(self)} condition on metric '{m}': {msg}".format(self.name, m, msg)
                problems.append(pb.Problem(types.Type.BAD_PRACTICE, severities.Severity.HIGH, msg))
        return problems

    def audit(self, audit_settings=None):
        my_name = str(self)
        util.logger.debug("Auditing %s", my_name)
        problems = []
        if self.is_built_in:
            return problems
        max_cond = int(util.get_setting(audit_settings, "audit.qualitygates.maxConditions", 8))
        nb_conditions = len(self.conditions())
        util.logger.debug("Auditing %s number of conditions (%d) is OK", my_name, nb_conditions)
        if nb_conditions == 0:
            rule = rules.get_rule(rules.RuleId.QG_NO_COND)
            msg = rule.msg.format(my_name)
            problems.append(pb.Problem(rule.type, rule.severity, msg))
        elif nb_conditions > max_cond:
            rule = rules.get_rule(rules.RuleId.QG_TOO_MANY_COND)
            msg = rule.msg.format(my_name, nb_conditions, max_cond)
            problems.append(pb.Problem(rule.type, rule.severity, msg))
        problems += self.__audit_conditions__()
        util.logger.debug("Auditing that %s has some assigned projects", my_name)
        if not self.is_default and not self.projects():
            rule = rules.get_rule(rules.RuleId.QG_NOT_USED)
            msg = rule.msg.format(my_name)
            problems.append(pb.Problem(rule.type, rule.severity, msg))
        return problems

    def to_json(self):
        json_data = {}
        if self.is_default:
            json_data["isDefault"] = True
        if self.is_built_in:
            json_data["isBuiltIn"] = True
        else:
            json_data["conditions"] = self.conditions(encoded=True)
            perms = self.permissions()
            if perms is not None and len(perms) > 0:
                for t in ("users", "groups"):
                    if t in perms:
                        perms[t] = util.list_to_csv(perms[t], ", ", True)
                json_data["permissions"] = util.remove_nones(perms)
        return json_data


def audit(endpoint=None, audit_settings=None):
    util.logger.info("--- Auditing quality gates ---")
    problems = []
    quality_gates_list = get_list(endpoint)
    max_qg = util.get_setting(audit_settings, "audit.qualitygates.maxNumber", 5)
    nb_qg = len(quality_gates_list)
    util.logger.debug("Auditing that there are no more than %s quality gates", str(max_qg))
    if nb_qg > max_qg:
        rule = rules.get_rule(rules.RuleId.QG_TOO_MANY_GATES)
        problems.append(pb.Problem(rule.type, rule.severity, rule.msg.format(nb_qg, 5)))
    for qg in quality_gates_list.values():
        problems += qg.audit(audit_settings)
    return problems


def get_list(endpoint):
    util.logger.info("Getting quality gates")
    data = json.loads(endpoint.get("qualitygates/list").text)
    qg_list = {}
    for qg in data["qualitygates"]:
        qg_obj = QualityGate(name=qg["name"], endpoint=endpoint, data=qg)
        if endpoint.version() < (7, 9, 0) and "default" in data and data["default"] == qg["id"]:
            qg_obj.is_default = True
        qg_list[qg_obj.name] = qg_obj
    return qg_list


def get_object(name, endpoint=None):
    if len(_QUALITY_GATES) == 0:
        get_list(endpoint)
    if name not in _MAP:
        return None
    return _QUALITY_GATES[_uuid(name, _MAP[name])]


def export(endpoint):
    util.logger.info("Exporting quality gates")
    qg_list = {}
    for k, qg in get_list(endpoint).items():
        qg_list[k] = qg.to_json()
    return qg_list


def create(name, endpoint=None, **kwargs):
    util.logger.info("Create quality gate '%s'", name)
    o = get_object(name=name, endpoint=endpoint)
    if o is None:
        o = QualityGate(name=name, endpoint=endpoint, create_data=kwargs)
    return o


def create_or_update(endpoint, name, **kwargs):
    o = get_object(endpoint=endpoint, name=name)
    if o is None:
        util.logger.debug("Quality gate '%s' does not exist, creating...", name)
        return create(name, endpoint, **kwargs)
    else:
        return o.update(**kwargs)


def import_config(endpoint, config_data):
    if "qualityGates" not in config_data:
        util.logger.info("No quality gates to import")
        return
    util.logger.info("Importing quality gates")
    for name, data in config_data["qualityGates"].items():
        create_or_update(endpoint, name, **data)


def count(endpoint):
    return len(get_list(endpoint))


def _encode_conditions(conds):
    simple_conds = []
    for c in conds:
        simple_conds.append(_encode_condition(c))
    return simple_conds


def _encode_condition(c):
    metric, op, val = c["metric"], c["op"], c["error"]
    if op == "GT":
        op = ">="
    elif op == "LT":
        op = "<="
    if metric.endswith("rating"):
        val = measures.get_rating_letter(val)
    return f"{metric} {op} {val}"


def _decode_condition(c):
    (metric, op, val) = c.strip().split(" ")
    if op in (">", ">="):
        op = "GT"
    elif op in ("<", "<="):
        op = "LT"
    if metric.endswith("rating"):
        val = measures.get_rating_number(val)
    return (metric, op, val)


def _uuid(name, id):
    return id


def search_by_name(endpoint, name):
    return util.search_by_name(endpoint, name, _SEARCH_API, "qualitygates")
