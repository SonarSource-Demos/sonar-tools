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
    Abstraction of the SonarQube setting concept
"""

import json
from sonar import sqobject, utilities

__SETTINGS = {}

class Setting(sqobject.SqObject):

    def __init__(self, key, endpoint, project=None, data=None):
        super().__init__(key, endpoint)
        self.project = project
        if data is None:
            params = {'keys': key}
            if project:
                params['component'] = project.key
            resp = self.get('api/settings/values', params=params)
            data = json.loads(resp.text)['settings']
        if data is not None:
            if 'inherited' in data:
                self.inherited = data['inherited']
            elif 'parentValues' in data or 'parentValue' in data:
                self.inherited = False
        __SETTINGS[self.uuid()] = self

    def uuid(self):
        return _uuid_p(self.key, self.project)

    def __str__(self):
        if self.project is None:
            return f"setting '{self.key}'"
        else:
            return f"setting '{self.key}' of {str(self.project)}"

    def set(self, value):
        params = {}
        if self.project:
            params['component'] = self.project.key
        return self.post('api/settings/set', params=params)


def get_object(key, endpoint=None, data=None, project=None):
    if key not in __SETTINGS:
        _ = Setting(key=key, endpoint=endpoint, data=data, project=project)
    return __SETTINGS[_uuid_p(key, project)]


def get_bulk(endpoint, settings_list=None, project=None):
    """Gets several settings as bulk (returns a dict)"""
    if isinstance(settings_list, list):
        params = {'keys': utilities.list_to_csv(settings_list)}
    else:
        params = {'keys': utilities.csv_normalize(settings_list)}
    if project:
        params['component'] = project.key
    resp = endpoint.get('api/settings/values', params=params)
    data = json.loads(resp.text)
    settings_dict = {}
    for s in data['settings']:
        o = Setting(s['key'], endpoint=endpoint, data=s, project=project)
        settings_dict[o.uuid()] = o
    return settings_dict

def uuid(key, project_key=None):
    """Computes uuid for a setting"""
    if project_key is None:
        return key
    else:
        return f"{key}#{project_key}"

def _uuid_p(key, project):
    """Computes uuid for a setting"""
    pk = None if project is None else project.key
    return uuid(key, pk)
