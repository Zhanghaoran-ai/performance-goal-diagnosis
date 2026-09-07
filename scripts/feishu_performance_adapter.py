#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""飞书绩效 HTTP API 适配器。

接口 URL、分页和字段映射由用户提供的 JSON 配置决定；凭证只从环境变量读取，
不会写入标准化数据、诊断报告或日志。仅使用 Python 标准库。
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime


class PerformanceAPIError(RuntimeError):
    pass


def get_path(data, path, default=None):
    if not path:
        return data
    cur = data
    for part in str(path).split('.'):
        if isinstance(cur, list) and part.isdigit():
            idx = int(part)
            if idx >= len(cur):
                return default
            cur = cur[idx]
        elif isinstance(cur, dict) and part in cur:
            cur = cur[part]
        else:
            return default
    return cur


def render_template(value, variables):
    if isinstance(value, str):
        try:
            return value.format(**variables)
        except KeyError as exc:
            raise PerformanceAPIError(f'接口配置引用了未提供的变量：{exc.args[0]}')
    if isinstance(value, list):
        return [render_template(v, variables) for v in value]
    if isinstance(value, dict):
        return {k: render_template(v, variables) for k, v in value.items()}
    return value


def mapped_value(item, spec, default=None):
    if spec is None:
        return default
    if isinstance(spec, list):
        for candidate in spec:
            value = mapped_value(item, candidate, None)
            if value not in (None, ''):
                return value
        return default
    if isinstance(spec, str):
        return get_path(item, spec, default)
    if isinstance(spec, dict):
        value = spec.get('constant') if 'constant' in spec else get_path(item, spec.get('path'), spec.get('default', default))
        if value in (None, ''):
            return value
        if spec.get('divide'):
            value = float(value) / float(spec['divide'])
        if spec.get('multiply'):
            value = float(value) * float(spec['multiply'])
        cast = spec.get('cast')
        if cast == 'str':
            value = str(value)
        elif cast == 'float':
            value = float(value)
        elif cast == 'int':
            value = int(float(value))
        elif cast == 'list' and not isinstance(value, list):
            value = [value]
        return value
    return spec


def as_list(value):
    if value in (None, ''):
        return []
    return value if isinstance(value, list) else [value]


class FeishuPerformanceCollector:
    """按声明式配置调用绩效接口并转换成诊断标准输入。"""

    DEFAULT_USER_MAPPING = {
        'user_id': ['user_id', 'open_id', 'employee_id', 'id'],
        'name': ['name', 'user_name', 'display_name'],
        'position': ['position', 'job_title'],
        'department': ['department.name', 'department_name', 'department'],
        'manager_id': ['manager_id', 'leader_id'],
        'level': ['level', 'job_level'],
    }
    DEFAULT_GOAL_MAPPING = {
        'goal_id': ['goal_id', 'objective_id', 'id'],
        'title': ['title', 'goal_name', 'objective_name', 'name'],
        'description': ['description', 'desc'],
        'level': ['level', 'goal_level'],
        'owner_id': ['owner_id', 'user_id', 'employee_id'],
        'owner_name': ['owner_name', 'user_name'],
        'department': ['department.name', 'department_name', 'department'],
        'parent_goal_ids': ['parent_goal_ids', 'parent_ids'],
        'aligned_to_goal_ids': ['aligned_to_goal_ids', 'aligned_goal_ids'],
        'progress': ['progress', 'completion_rate'],
        'status': ['status'],
        'weight': ['weight'],
    }
    DEFAULT_INDICATOR_MAPPING = {
        'indicator_id': ['indicator_id', 'metric_id', 'id'],
        'name': ['name', 'indicator_name', 'metric_name'],
        'value': ['target_value', 'value', 'current_value'],
        'unit': ['unit'],
        'parent_indicator_ids': ['parent_indicator_ids', 'parent_metric_ids'],
    }

    def __init__(self, config, variables=None, transport=None, sleep=time.sleep):
        self.config = config or {}
        self.variables = dict(variables or {})
        self.transport = transport or self._default_transport
        self.sleep = sleep
        self.warnings = []
        self._token = None
        self._validate_config()

    @classmethod
    def from_file(cls, path, variables=None, transport=None):
        with open(path, 'r', encoding='utf-8') as f:
            return cls(json.load(f), variables=variables, transport=transport)

    def _validate_config(self):
        if not self.config.get('base_url'):
            raise PerformanceAPIError('绩效接口配置缺少 base_url')
        if not isinstance(self.config.get('endpoints'), dict):
            raise PerformanceAPIError('绩效接口配置缺少 endpoints')
        if 'performance' not in self.config['endpoints']:
            raise PerformanceAPIError('endpoints.performance 为必填项')
        auth = self.config.get('auth', {'type': 'none'})
        auth_type = auth.get('type', 'none')
        if auth_type not in ('none', 'bearer_env', 'tenant_access_token'):
            raise PerformanceAPIError(f'不支持的鉴权类型：{auth_type}')
        forbidden = ('token', 'app_secret', 'authorization')
        for key in forbidden:
            if key in auth:
                raise PerformanceAPIError(f'禁止在配置文件中保存明文凭证字段：auth.{key}；请改用环境变量')
        if auth_type == 'bearer_env' and not auth.get('token_env'):
            raise PerformanceAPIError('bearer_env 鉴权必须提供 auth.token_env')
        if auth_type == 'tenant_access_token' and not (auth.get('app_id_env') and auth.get('app_secret_env')):
            raise PerformanceAPIError('tenant_access_token 鉴权必须提供 app_id_env 和 app_secret_env')

    def _default_transport(self, url, method, headers, body, timeout, max_response_bytes):
        payload = None if body is None else json.dumps(body, ensure_ascii=False).encode('utf-8')
        req = urllib.request.Request(url, data=payload, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read(max_response_bytes + 1)
                if len(raw) > max_response_bytes:
                    raise PerformanceAPIError(f'接口响应超过大小上限 {max_response_bytes} bytes')
                return json.loads(raw.decode('utf-8'))
        except urllib.error.HTTPError as exc:
            raise PerformanceAPIError(f'绩效接口 HTTP {exc.code}：{exc.reason}')
        except urllib.error.URLError as exc:
            raise PerformanceAPIError(f'绩效接口不可访问：{exc.reason}')
        except json.JSONDecodeError:
            raise PerformanceAPIError('绩效接口未返回合法 JSON')

    def _absolute_url(self, path):
        url = urllib.parse.urljoin(self.config['base_url'].rstrip('/') + '/', str(path).lstrip('/'))
        parsed = urllib.parse.urlparse(url)
        if parsed.scheme not in ('http', 'https') or not parsed.netloc:
            raise PerformanceAPIError('接口 URL 必须是合法的 http/https 地址')
        return url

    def _auth_headers(self):
        auth = self.config.get('auth', {'type': 'none'})
        auth_type = auth.get('type', 'none')
        if auth_type == 'none':
            return {}
        if auth_type == 'bearer_env':
            token = os.environ.get(auth['token_env'])
            if not token:
                raise PerformanceAPIError(f'未设置凭证环境变量：{auth["token_env"]}')
            return {auth.get('header', 'Authorization'): auth.get('prefix', 'Bearer ') + token}
        if self._token:
            return {'Authorization': 'Bearer ' + self._token}
        app_id = os.environ.get(auth['app_id_env'])
        app_secret = os.environ.get(auth['app_secret_env'])
        if not app_id or not app_secret:
            raise PerformanceAPIError('未设置 App ID/App Secret 环境变量')
        token_path = auth.get('token_path', '/open-apis/auth/v3/tenant_access_token/internal')
        response = self.transport(
            self._absolute_url(token_path), 'POST', {'Content-Type': 'application/json'},
            {'app_id': app_id, 'app_secret': app_secret},
            int(self.config.get('timeout_seconds', 30)), int(self.config.get('max_response_bytes', 10485760)),
        )
        self._token = get_path(response, auth.get('token_response_path', 'tenant_access_token'))
        if not self._token:
            raise PerformanceAPIError('鉴权响应中未找到 tenant_access_token')
        return {'Authorization': 'Bearer ' + self._token}

    def _check_success(self, response, endpoint):
        success = endpoint.get('success') or self.config.get('success')
        if not success:
            return
        actual = get_path(response, success.get('path', 'code'))
        expected = success.get('equals', 0)
        if actual != expected:
            message = get_path(response, success.get('message_path', 'msg'), '接口返回失败')
            raise PerformanceAPIError(f'绩效接口业务错误：{message}（code={actual}）')

    def _request_page(self, endpoint, variables, page_token=None):
        endpoint = render_template(endpoint, variables)
        method = endpoint.get('method', 'GET').upper()
        params = dict(endpoint.get('query') or {})
        body = dict(endpoint.get('body') or {}) if endpoint.get('body') is not None else None
        pagination = endpoint.get('pagination') or {}
        if pagination.get('page_size_param'):
            target = body if method != 'GET' and body is not None else params
            target[pagination['page_size_param']] = pagination.get('page_size', 100)
        if page_token not in (None, '') and pagination.get('request_token_param'):
            target = body if method != 'GET' and body is not None else params
            target[pagination['request_token_param']] = page_token
        url = self._absolute_url(endpoint.get('path', ''))
        if params:
            url += ('&' if '?' in url else '?') + urllib.parse.urlencode(params, doseq=True)
        headers = {'Accept': 'application/json'}
        if body is not None:
            headers['Content-Type'] = 'application/json'
        headers.update(self._auth_headers())
        for header, env_name in (endpoint.get('header_env') or {}).items():
            value = os.environ.get(env_name)
            if not value:
                raise PerformanceAPIError(f'未设置请求头环境变量：{env_name}')
            headers[header] = value
        attempts = max(1, int(endpoint.get('retry', 1)) + 1)
        last_error = None
        for attempt in range(attempts):
            try:
                response = self.transport(
                    url, method, headers, body,
                    int(endpoint.get('timeout_seconds', self.config.get('timeout_seconds', 30))),
                    int(self.config.get('max_response_bytes', 10485760)),
                )
                self._check_success(response, endpoint)
                return response
            except PerformanceAPIError as exc:
                last_error = exc
                if attempt + 1 < attempts:
                    self.sleep(min(2 ** attempt, 4))
        raise last_error

    def _fetch_endpoint(self, endpoint, variables):
        all_items = []
        page_token = None
        pagination = endpoint.get('pagination') or {}
        max_pages = min(int(pagination.get('max_pages', 100)), 1000)
        for _ in range(max_pages):
            response = self._request_page(endpoint, variables, page_token)
            items = get_path(response, endpoint.get('items_path', 'data.items'), [])
            if not isinstance(items, list):
                raise PerformanceAPIError(f'items_path 未指向数组：{endpoint.get("items_path", "data.items")}')
            all_items.extend(items)
            if not pagination:
                break
            has_more = get_path(response, pagination.get('has_more_path', 'data.has_more'), False)
            next_token = get_path(response, pagination.get('response_token_path', 'data.page_token'))
            if not has_more or next_token in (None, '') or next_token == page_token:
                break
            page_token = next_token
        else:
            self.warnings.append(f'接口分页达到上限 {max_pages} 页，结果可能不完整')
        return all_items

    def _normalize_user(self, raw):
        mapping = dict(self.DEFAULT_USER_MAPPING)
        mapping.update((self.config.get('mappings') or {}).get('user') or {})
        user = {key: mapped_value(raw, spec, '') for key, spec in mapping.items()}
        user['user_id'] = str(user.get('user_id') or '')
        user['name'] = str(user.get('name') or '')
        if not user['user_id']:
            self.warnings.append('发现缺少 user_id 的人员记录，已跳过')
            return None
        return user

    def _normalize_indicator(self, raw):
        mapping = dict(self.DEFAULT_INDICATOR_MAPPING)
        mapping.update((self.config.get('mappings') or {}).get('indicator') or {})
        indicator = {key: mapped_value(raw, spec, None) for key, spec in mapping.items()}
        indicator['name'] = str(indicator.get('name') or '').strip()
        if not indicator['name']:
            self.warnings.append('发现缺少指标名称的记录，已跳过')
            return None
        if indicator.get('indicator_id') not in (None, ''):
            indicator['indicator_id'] = str(indicator['indicator_id'])
        indicator['parent_indicator_ids'] = [str(v) for v in as_list(indicator.get('parent_indicator_ids')) if v not in (None, '')]
        return indicator

    def _normalize_goal(self, raw, index):
        mappings = self.config.get('mappings') or {}
        mapping = dict(self.DEFAULT_GOAL_MAPPING)
        mapping.update(mappings.get('goal') or {})
        goal = {key: mapped_value(raw, spec, None) for key, spec in mapping.items()}
        goal['goal_id'] = str(goal.get('goal_id') or f'FEISHU-G-{index:06d}')
        if not mapped_value(raw, mapping.get('goal_id'), None):
            self.warnings.append(f'绩效记录缺少 goal_id，已生成 {goal["goal_id"]}')
        goal['title'] = str(goal.get('title') or '未命名绩效目标')
        goal['owner_id'] = str(goal.get('owner_id') or '')
        goal['owner_name'] = str(goal.get('owner_name') or '')
        goal['level'] = str(goal.get('level') or 'L?')
        goal['parent_goal_ids'] = [str(v) for v in as_list(goal.get('parent_goal_ids')) if v not in (None, '')]
        goal['aligned_to_goal_ids'] = [str(v) for v in as_list(goal.get('aligned_to_goal_ids')) if v not in (None, '')]
        indicators_path = mappings.get('indicators_path', 'indicators')
        indicator_rows = get_path(raw, indicators_path, [])
        if not isinstance(indicator_rows, list):
            indicator_rows = []
            self.warnings.append(f'目标 {goal["goal_id"]} 的指标路径不是数组：{indicators_path}')
        goal['indicators'] = [x for x in (self._normalize_indicator(v) for v in indicator_rows) if x]
        return goal

    def collect(self):
        endpoints = self.config['endpoints']
        users_raw = []
        if endpoints.get('users'):
            users_raw = self._fetch_endpoint(endpoints['users'], self.variables)
        users = [x for x in (self._normalize_user(v) for v in users_raw) if x]

        perf_endpoint = endpoints['performance']
        mode = perf_endpoint.get('mode', 'list')
        performance_rows = []
        if mode == 'per_user':
            if not users:
                raise PerformanceAPIError('performance.mode=per_user 时必须先成功获取用户列表')
            for user in users:
                variables = dict(self.variables)
                variables.update(user)
                performance_rows.extend(self._fetch_endpoint(perf_endpoint, variables))
        elif mode == 'list':
            performance_rows = self._fetch_endpoint(perf_endpoint, self.variables)
        else:
            raise PerformanceAPIError(f'不支持的 performance.mode：{mode}')

        item_mode = (self.config.get('mappings') or {}).get('performance_item_mode', 'goal_with_indicators')
        if item_mode == 'indicator_rows':
            goals_by_id = {}
            for index, raw in enumerate(performance_rows, 1):
                goal = self._normalize_goal(dict(raw, indicators=[]), index)
                indicator = self._normalize_indicator(raw)
                existing = goals_by_id.setdefault(goal['goal_id'], goal)
                if indicator:
                    existing['indicators'].append(indicator)
            goals = list(goals_by_id.values())
        else:
            goals = [self._normalize_goal(raw, index) for index, raw in enumerate(performance_rows, 1)]

        user_map = {u['user_id']: u for u in users}
        for goal in goals:
            user = user_map.get(goal.get('owner_id'), {})
            goal['owner_name'] = goal.get('owner_name') or user.get('name', '')
            goal['department'] = goal.get('department') or user.get('department', '')

        return {
            'meta': {
                'collect_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'source': 'feishu_performance_api',
                'permission_level': int(self.config.get('permission_level', 2)),
                'total_users': len(users),
                'users_with_okr': len({g.get('owner_id') for g in goals if g.get('owner_id')}),
                'total_goals': len(goals),
                'warnings': self.warnings,
            },
            'users': users,
            'goals': goals,
            'indicator_relations': self.config.get('indicator_relations', []),
        }


def parse_variables(values):
    result = {}
    for value in values or []:
        if '=' not in value:
            raise PerformanceAPIError(f'变量格式应为 KEY=VALUE：{value}')
        key, item = value.split('=', 1)
        if not key:
            raise PerformanceAPIError('变量名不能为空')
        result[key] = item
    return result
