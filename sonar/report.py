import markdown
from collections import defaultdict
from markdown import markdown

MARKDOWN_PATH = __file__.replace('report.py', 'template.md')


def generate_mappings(project_mapping):
    projects = list()
    profile_mapping = defaultdict(set)
    gate_mapping = defaultdict(set)
    ci_mapping = defaultdict(set)
    devops_mapping = defaultdict(set)

    for project in project_mapping.values():
        for k, v in project.get('qualityProfiles', dict()).items():
            profile_mapping[k + v].add(project['name'])
        gate_mapping[project.get('qualityGate')].add(project['name'])
        if project.get('detectedCi') not in [None, 'unknown', 'undetected']:
            ci_mapping[project.get('detectedCi')].add(project['name'])
        devops_mapping[project.get('binding', dict()).get('key')].add(project['name'])
        projects.append(
            dict(name=project['name'],
                 template_issues=project.get('issues', dict()).get('instantiatedRules', 0),
                 plugin_issues=sum(project.get('issues', dict()).get('thirdParty', dict()).values()) if isinstance(
                     project.get('issues', dict()).get('thirdParty', dict()), dict) else project.get('issues',
                                                                                                     dict()).get(
                     'thirdParty', 0),
                 binding=project.get('binding', dict()).get('key', '')
                 )
        )
    return projects, profile_mapping, gate_mapping, ci_mapping, devops_mapping


def evaluate_sast_config(config):
    return "SAST Configuration Detected" if any(
        [v for k, v in config.get('globalSettings', dict()).get('sastConfig', dict()).items()] + [
            i.get('sastConfig') for i
            in config['projects'].values()
        ]) else "No SAST Configuration Detected"


def calculate_orphan_issues(config):
    return sum(
        [
            v if isinstance(v, int) else sum([x for x in v.values()]) for i in config['projects'].values() for k, v in
            i.get('issues', dict()).items() if k in ['instantiatedRules', 'thirdParty']
        ]
    )


def format_devops_bindings(devops_mapping, config):
    return "\n".join([
        "| {name} | {project_count} | | |".format(name=k, project_count=len(devops_mapping[k])) for k, v in
        config.get('globalSettings', dict()).get('devopsIntegration', dict()).items()
    ])


def format_pipelines(ci_mapping):
    return "\n".join([
        "| {name} | {project_count} |".format(name=k, project_count=len(v)) for k, v in ci_mapping.items()
    ])


def format_permission_templates(config):
    return "\n".join([
        "| {name} | {description} | {pattern} | {defaults} |".format(name=k, description=v.get('description', ""),
                                                                     pattern=v.get('pattern', ""),
                                                                     defaults=v.get('defaultFor', "")) for k, v in
        config.get('globalSettings', dict()).get('permissionTemplates', dict()).items()
    ])


def format_applications(config):
    return "\n".join(
        ["| {name} | {project_count} |".format(
            name=i['name'],
            project_count=len(
                set(
                    [
                        project for branch in i.get('branches', dict()).values() for project in
                        branch.get('projects', dict()).keys()
                    ]
                )
            )
        ) for i in
            config.get('applications', dict()).values()])


def format_profiles(profile_mapping, config):
    return "\n".join([
        "| {name} | {language} | {template_rules} | {plugin_rules} | {project_count} |".format(
            name=profile,
            template_rules="",
            plugin_rules="", language=k,
            project_count=len(profile_mapping[k + profile])
        ) for k, v in config.get("qualityProfiles", dict()).items()
        for profile, values in v.items() if not values.get('isBuiltIn', False)
    ])


def format_gates(gate_mapping):
    return "\n".join([
        "| {name} | {project_count} |".format(
            name=name,
            project_count=len(projects)
        ) for name, projects in gate_mapping.items() if name is not None
    ])


def generate_markdown(config):
    with open(MARKDOWN_PATH, 'rt') as f:
        template_content = f.read()

    projects, profile_mapping, gate_mapping, ci_mapping, devops_mapping = generate_mappings(
        project_mapping=config.get('projects', dict()))
    md = template_content.format(
        server_version="{edition} {version}".format(edition=config['platform']['edition'],
                                                    version=config['platform']['version']),
        server_url=config['platform']['url'],
        project_count=len(config['projects']),
        lines_of_code=sum([i.get('ncloc', dict()).get('total', 0) for i in config['projects'].values()]),
        user_count=len(config['users']),
        auth_method="",
        orphan_issues=calculate_orphan_issues(config=config),
        devops_bindings=format_devops_bindings(devops_mapping=devops_mapping, config=config),
        pipelines=format_pipelines(ci_mapping=ci_mapping),
        permission_templates=format_permission_templates(config=config),
        quality_profiles=format_profiles(profile_mapping=profile_mapping, config=config),
        quality_gates=format_gates(gate_mapping=gate_mapping),
        portfolios="\n".join([
            "| {name} | | {project_count} |".format(
                name=i['name'],
                project_count=None
            ) for i in
            config.get('portfolios', dict()).values()
        ]),
        applications=format_applications(config=config),
        plugins="\n".join([
            "| {name} | {description} | {version} | {url} |".format(name=i.split('[')[1].replace(']', ''),
                                                                    description="",
                                                                    version=i.split('[')[0].strip(), url="") for i in
            config['platform'].get('plugins', dict()).values()
        ]),
        project_metrics="\n".join([
            "| {name} | {template_issues} | {plugin_issues} | {binding} |".format(**project) for project in projects if
            project['template_issues'] + project['plugin_issues'] > 0
        ]),
        sast_configued=evaluate_sast_config(config=config),
        total_issues=None,
        safe_hotspots=sum([i.get('hotspots', dict()).get('safe', 0) for i in config['projects'].values()]),
        fixed_hotspots=sum([i.get('hotspots', dict()).get('fixed', 0) for i in config['projects'].values()]),
        accepted_issues=sum(
            [v for i in config['projects'].values() for k, v in i.get('issues', dict()).items() if k in ['accepted']]),
        false_positives=sum(
            [v for i in config['projects'].values() for k, v in i.get('issues', dict()).items() if
             k in ['falsePositives']]),
    )
    return md


def html_export(file_pointer, config):
    md = generate_markdown(config)
    return markdown(md, extensions=['tables'])
