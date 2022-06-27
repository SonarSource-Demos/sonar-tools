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

from sonar import utilities
from sonar.permissions import permissions
from sonar.audit import rules, problem

PROJECT_PERMISSIONS = {
    "user": "Browse",
    "codeviewer": "See source code",
    "issueadmin": "Administer Issues",
    "securityhotspotadmin": "Create Projects",
    "scan": "Execute Analysis",
    "admin": "Administer Project",
}


class ProjectPermissions(permissions.Permissions):
    API_GET = {"users": "permissions/users", "groups": "permissions/groups"}
    API_SET = {"users": "permissions/add_user", "groups": "permissions/add_group"}
    API_REMOVE = {"users": "permissions/remove_user", "groups": "permissions/remove_group"}
    API_GET_FIELD = {"users": "login", "groups": "name"}
    API_SET_FIELD = {"users": "login", "groups": "groupName"}

    def __init__(self, concerned_object):
        self.concerned_object = concerned_object
        super().__init__(concerned_object.endpoint)

    def __str__(self):
        return f"permissions of {str(self.concerned_object)}"

    def read(self, perm_type=None):
        self.permissions = permissions.NO_PERMISSIONS
        for p in permissions.normalize(perm_type):
            self.permissions[p] = self._get_api(
                ProjectPermissions.API_GET[p], p, ProjectPermissions.API_GET_FIELD[p], projectKey=self.concerned_object.key, ps=permissions.MAX_PERMS
            )
        self._remove_aggregations_creator()
        return self

    def set(self, new_perms):
        utilities.logger.debug("Setting %s with %s", str(self), str(new_perms))
        if self.permissions is None:
            self.read()
        for p in permissions.PERMISSION_TYPES:
            if new_perms is None or p not in new_perms:
                continue
            decoded_perms = {k: permissions.decode(v) for k, v in new_perms[p].items()}
            to_remove = permissions.diff(self.permissions[p], decoded_perms)
            self._post_api(ProjectPermissions.API_REMOVE[p], ProjectPermissions.API_SET_FIELD[p], to_remove, projectKey=self.concerned_object.key)
            to_add = permissions.diff(decoded_perms, self.permissions[p])
            self._post_api(ProjectPermissions.API_SET[p], ProjectPermissions.API_SET_FIELD[p], to_add, projectKey=self.concerned_object.key)
        return self.read()

    def audit(self, audit_settings):
        if not audit_settings["audit.projects.permissions"]:
            utilities.logger.debug("Auditing project permissions is disabled by configuration, skipping")
            return []
        utilities.logger.debug("Auditing %s permissions", str(self))
        return self.__audit_user_permissions(audit_settings) + self.__audit_group_permissions(audit_settings)

    def __audit_user_permissions(self, audit_settings):
        problems = []
        user_count = self.count("users")
        max_users = audit_settings["audit.projects.permissions.maxUsers"]
        if user_count > max_users:
            rule = rules.get_rule(rules.RuleId.PROJ_PERM_MAX_USERS)
            msg = rule.msg.format(str(self.concerned_object), user_count)
            problems.append(problem.Problem(rule.type, rule.severity, msg, concerned_object=self))

        max_admins = audit_settings["audit.projects.permissions.maxAdminUsers"]
        admin_count = self.count("users", ("admin"))
        if admin_count > max_admins:
            rule = rules.get_rule(rules.RuleId.PROJ_PERM_MAX_ADM_USERS)
            msg = rule.msg.format(str(self.concerned_object), admin_count, max_admins)
            problems.append(problem.Problem(rule.type, rule.severity, msg, concerned_object=self))

        return problems

    def __audit_group_permissions(self, audit_settings):
        problems = []
        groups = self.read().to_json(perm_type="groups")
        for gr_name, gr_perms in groups.items():
            if gr_name == "Anyone":
                rule = rules.get_rule(rules.RuleId.PROJ_PERM_ANYONE)
                problems.append(problem.Problem(rule.type, rule.severity, rule.msg.format(str(self)), concerned_object=self))
            if gr_name == "sonar-users" and (
                "issueadmin" in gr_perms or "scan" in gr_perms or "securityhotspotadmin" in gr_perms or "admin" in gr_perms
            ):
                rule = rules.get_rule(rules.RuleId.PROJ_PERM_SONAR_USERS_ELEVATED_PERMS)
                problems.append(problem.Problem(rule.type, rule.severity, rule.msg.format(str(self.concerned_object)), concerned_object=self.concerned_object))

        max_perms = audit_settings["audit.projects.permissions.maxGroups"]
        counter = self.count(perm_type="groups", perm_filter=permissions.PROJECT_PERMISSIONS)
        if counter > max_perms:
            rule = rules.get_rule(rules.RuleId.PROJ_PERM_MAX_GROUPS)
            msg = rule.msg.format(str(self.concerned_object), counter, max_perms)
            problems.append(problem.Problem(rule.type, rule.severity, msg, concerned_object=self))

        max_scan = audit_settings["audit.projects.permissions.maxScanGroups"]
        counter = self.count(perm_type="groups", perm_filter=("scan"))
        if counter > max_scan:
            rule = rules.get_rule(rules.RuleId.PROJ_PERM_MAX_SCAN_GROUPS)
            msg = rule.msg.format(str(self.concerned_object), counter, max_scan)
            problems.append(problem.Problem(rule.type, rule.severity, msg, concerned_object=self))

        max_issue_adm = audit_settings["audit.projects.permissions.maxIssueAdminGroups"]
        counter = self.count(perm_type="groups", perm_filter=("issueadmin"))
        if counter > max_issue_adm:
            rule = rules.get_rule(rules.RuleId.PROJ_PERM_MAX_ISSUE_ADM_GROUPS)
            msg = rule.msg.format(str(self.concerned_object), counter, max_issue_adm)
            problems.append(problem.Problem(rule.type, rule.severity, msg, concerned_object=self))

        max_spots_adm = audit_settings["audit.projects.permissions.maxHotspotAdminGroups"]
        counter = self.count(perm_type="groups", perm_filter=("securityhotspotadmin"))
        if counter > max_spots_adm:
            rule = rules.get_rule(rules.RuleId.PROJ_PERM_MAX_HOTSPOT_ADM_GROUPS)
            msg = rule.msg.format(str(self.concerned_object), counter, max_spots_adm)
            problems.append(problem.Problem(rule.type, rule.severity, msg, concerned_object=self))

        max_admins = audit_settings["audit.projects.permissions.maxAdminGroups"]
        counter = self.count(perm_type="groups", perm_filter=("admin"))
        if counter > max_admins:
            rule = rules.get_rule(rules.RuleId.PROJ_PERM_MAX_ADM_GROUPS)
            msg = rule.msg.format(str(self.concerned_object), counter, max_admins)
            problems.append(problem.Problem(rule.type, rule.severity, msg, concerned_object=self))
        return problems
