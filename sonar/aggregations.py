#
# sonar-tools
# Copyright (C) 2022 Olivier Korach
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

    Parent class of applications and portfolios

"""
import json
from sonar import env
import sonar.components as comp
import sonar.utilities as util
from sonar.audit import rules, problem


class Aggregation(comp.Component):
    def __init__(self, key, endpoint, data=None):
        self._nbr_projects = None
        self._id = None
        self._visibility = None
        super().__init__(key, endpoint)

    def _load(self, data=None, api=None, key_name="key"):
        """Loads an aggregation object with contents of data"""
        if self._json is None and data is not None:
            self._json = data
        if self._json is None:
            self._json = json.loads(self.get(api, params={key_name: self.key}).text)
        self._id = self.key
        self.name = self._json.get("name", None)
        self._visibility = self._json.get("visibility", None)

    def visibility(self):
        if self._visibility is None:
            self._load()
        return self._visibility

    def nbr_projects(self):
        if self._nbr_projects is None:
            data = json.loads(self.get("measures/component", params={"component": self.key, "metricKeys": "projects,ncloc"},).text)[
                "component"
            ]["measures"]
            for m in data:
                if m["metric"] == "projects":
                    self._nbr_projects = int(m["value"])
                elif m["metric"] == "ncloc":
                    self._ncloc = int(m["value"])
        return self._nbr_projects

    def _audit_aggregation_cardinality(self, sizes, broken_rule):
        problems = []
        n = self.nbr_projects()
        if n in sizes:
            rule = rules.get_rule(broken_rule)
            msg = rule.msg.format(str(self))
            problems.append(problem.Problem(rule.type, rule.severity, msg, concerned_object=self))
        else:
            util.logger.debug("%s has %d projects", str(self), n)
        return problems

    def _audit_empty_aggregation(self, broken_rule):
        return self._audit_aggregation_cardinality((0, None), broken_rule)

    def _audit_singleton_aggregation(self, broken_rule):
        return self._audit_aggregation_cardinality((1, 1), broken_rule)


def count(api, endpoint, params=None):
    if params is None:
        params = {}
    params["ps"] = 1
    data = json.loads(endpoint.get(api, params=params).text)
    return data["paging"]["total"]
