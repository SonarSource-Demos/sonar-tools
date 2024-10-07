# SonarQube Utilization Assessment

# Instance Overview

* Server Base URL \-\> {server_url}  
* {server_version}
* {project_count} Projects
* {lines_of_code} lines of code  
* {user_count} users  
* {orphan_issues} issues that cannot be migrated 
{auth_method}


# DevOps Integrations

## {server_url}

| DevOps Platform Binding | \# Projects | Multi-branchProjects? | PR Projects? |
| :---- | :---- | :---- | :---- |
{devops_bindings}

# CI Environment

## {server_url}

| CI Tool | \# Projects | Scans per day |
| :---- | :---- | :---- |
{pipelines}

# Permissions

## Permission Templates

| Template Name | Description | Project key pattern | Default For|
| :---- | :---- | :---- | :---- |
{permission_templates}

# Governance

## Custom Quality Profiles

| Quality Profile Name | Language | Template Rules | Rules from 3rd party plugins | \# of Projects using |
| :---- | :---- | :---- | :---- | :---- |
{quality_profiles}

## Custom Quality Gates

| Quality Gate Name | \# of Projects using |
| :---- | :---- |
{quality_gates}

## Portfolios

| Portfolio Name | Project selection type | \# of Projects | 
| :---- | :---- | :---- |
{portfolios}

## Applications

| Application Name | \# of Projects |
| :---- | :---- |
{applications}

# Installed Plugins

| Plugin Name | Description | Version | Home Page URL |
| :---- | :---- | :---- | :---- |
{plugins}

# Project Metrics

| Project Name | Template Issues | Plugin Issues | Devops Binding |
|:-------------|:----------------|:--------------|:---------------|
 {project_metrics}

## Details

* {sast_configued}  
* {total_issues} of Total Issues   
* {safe_hotspots} Hotspots Marked Safe  
* {fixed_hotspots} Hotspots Fixed
* {accepted_issues} Issues Accepted  
* {false_positives} False Positives   