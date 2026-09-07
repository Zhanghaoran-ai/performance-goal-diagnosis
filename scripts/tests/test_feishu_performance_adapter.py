# -*- coding: utf-8 -*-
"""飞书绩效配置适配器：鉴权、分页、字段映射与敏感信息边界。"""

import json
import os
import sys

import pytest

_SCRIPTS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)

from feishu_performance_adapter import (
    FeishuPerformanceCollector,
    PerformanceAPIError,
    parse_variables,
)


def base_config():
    return {
        'base_url': 'https://example.test',
        'auth': {'type': 'bearer_env', 'token_env': 'TEST_PERF_TOKEN'},
        'success': {'path': 'code', 'equals': 0, 'message_path': 'msg'},
        'endpoints': {
            'users': {
                'method': 'GET', 'path': '/users', 'items_path': 'data.items',
                'pagination': {
                    'page_size_param': 'page_size', 'page_size': 1,
                    'request_token_param': 'page_token',
                    'response_token_path': 'data.page_token',
                    'has_more_path': 'data.has_more',
                },
            },
            'performance': {
                'mode': 'list', 'method': 'GET', 'path': '/performance',
                'items_path': 'data.items',
            },
        },
        'mappings': {'indicators_path': 'metrics'},
    }


def test_rejects_plaintext_secret_in_config():
    cfg = base_config()
    cfg['auth'] = {'type': 'bearer_env', 'token_env': 'TOKEN', 'app_secret': 'forbidden'}
    with pytest.raises(PerformanceAPIError, match='明文凭证'):
        FeishuPerformanceCollector(cfg)


def test_missing_environment_token_fails_without_leaking_value(monkeypatch):
    monkeypatch.delenv('TEST_PERF_TOKEN', raising=False)
    with pytest.raises(PerformanceAPIError, match='TEST_PERF_TOKEN') as exc:
        FeishuPerformanceCollector(base_config(), transport=lambda *_: {}).collect()
    assert 'Bearer' not in str(exc.value)


def test_pagination_and_mapping(monkeypatch):
    monkeypatch.setenv('TEST_PERF_TOKEN', 'UNIT_TEST_SENTINEL')
    calls = []

    def transport(url, method, headers, body, timeout, limit):
        calls.append((url, headers))
        if '/users' in url:
            if 'page_token=next' in url:
                return {'code': 0, 'data': {'items': [
                    {'user_id': 'U2', 'name': '乙', 'department_name': '客户成功', 'leader_id': 'U1'}
                ], 'has_more': False}}
            return {'code': 0, 'data': {'items': [
                {'user_id': 'U1', 'name': '甲', 'department_name': '客户成功'}
            ], 'has_more': True, 'page_token': 'next'}}
        return {'code': 0, 'data': {'items': [
            {
                'id': 'G1', 'name': '提升续约', 'user_id': 'U2', 'level': 'L3',
                'metrics': [
                    {'metric_id': 'I1', 'metric_name': '续约率', 'target_value': 92, 'unit': '%'}
                ],
            }
        ]}}

    data = FeishuPerformanceCollector(base_config(), transport=transport).collect()
    assert data['meta']['total_users'] == 2
    assert data['meta']['total_goals'] == 1
    assert data['goals'][0]['owner_name'] == '乙'
    assert data['goals'][0]['department'] == '客户成功'
    assert data['goals'][0]['indicators'][0]['indicator_id'] == 'I1'
    assert len([c for c in calls if '/users' in c[0]]) == 2
    assert all(c[1]['Authorization'] == 'Bearer UNIT_TEST_SENTINEL' for c in calls)
    assert 'UNIT_TEST_SENTINEL' not in json.dumps(data, ensure_ascii=False)


def test_per_user_mode_renders_user_variable(monkeypatch):
    monkeypatch.setenv('TEST_PERF_TOKEN', 'secret')
    cfg = base_config()
    cfg['endpoints']['users'].pop('pagination')
    cfg['endpoints']['performance'].update({'mode': 'per_user', 'path': '/users/{user_id}/goals'})
    seen = []

    def transport(url, method, headers, body, timeout, limit):
        seen.append(url)
        if url.endswith('/users'):
            return {'code': 0, 'data': {'items': [{'user_id': 'U1', 'name': '甲'}]}}
        return {'code': 0, 'data': {'items': []}}

    FeishuPerformanceCollector(cfg, transport=transport).collect()
    assert any(url.endswith('/users/U1/goals') for url in seen)


def test_indicator_rows_are_grouped(monkeypatch):
    monkeypatch.setenv('TEST_PERF_TOKEN', 'secret')
    cfg = base_config()
    cfg['endpoints'].pop('users')
    cfg['mappings'] = {
        'performance_item_mode': 'indicator_rows',
        'goal': {'goal_id': 'goal.id', 'title': 'goal.title', 'owner_id': 'owner_id'},
        'indicator': {'indicator_id': 'metric_id', 'name': 'metric_name'},
    }

    def transport(*_args):
        return {'code': 0, 'data': {'items': [
            {'goal': {'id': 'G1', 'title': '增长'}, 'owner_id': 'U1', 'metric_id': 'I1', 'metric_name': '续约率'},
            {'goal': {'id': 'G1', 'title': '增长'}, 'owner_id': 'U1', 'metric_id': 'I2', 'metric_name': '增购率'},
        ]}}

    data = FeishuPerformanceCollector(cfg, transport=transport).collect()
    assert len(data['goals']) == 1
    assert [x['indicator_id'] for x in data['goals'][0]['indicators']] == ['I1', 'I2']


def test_parse_variables():
    assert parse_variables(['cycle_id=C1', 'department_id=D1']) == {
        'cycle_id': 'C1', 'department_id': 'D1'
    }
    with pytest.raises(PerformanceAPIError):
        parse_variables(['broken'])
