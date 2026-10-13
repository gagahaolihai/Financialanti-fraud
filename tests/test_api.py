"""API 集成测试"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pytest
from app import app


@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client


class TestAPI:
    """API 端点测试"""

    def test_health_check(self, client):
        resp = client.get('/api/health')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "ok"
        assert "version" in data

    def test_chat_greeting(self, client):
        resp = client.post('/api/chat', json={"message": "__init__"})
        assert resp.status_code == 200
        data = resp.get_json()
        assert "response" in data
        assert data["type"] == "greeting"

    def test_chat_normal(self, client):
        resp = client.post('/api/chat', json={"message": "你好"})
        assert resp.status_code == 200
        data = resp.get_json()
        assert len(data["response"]) > 0
        assert "suggestions" in data

    def test_chat_empty_message(self, client):
        resp = client.post('/api/chat', json={"message": ""})
        assert resp.status_code == 200

    def test_knowledge_types(self, client):
        resp = client.get('/api/knowledge/types')
        assert resp.status_code == 200
        data = resp.get_json()
        assert "fraud_types" in data
        assert len(data["fraud_types"]) > 0

    def test_scenario_list(self, client):
        resp = client.get('/api/scenario/list')
        assert resp.status_code == 200
        data = resp.get_json()
        assert "scenarios" in data

    def test_report_url_missing(self, client):
        resp = client.post('/api/report/url', json={"url": ""})
        assert resp.status_code == 400

    def test_report_url_suspicious(self, client):
        resp = client.post('/api/report/url', json={"url": "http://anquan-zhongxin.com"})
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["url_analysis"]["is_suspicious"] is True

    def test_user_profile(self, client):
        resp = client.get('/api/user/profile?user_id=test')
        assert resp.status_code == 200
        data = resp.get_json()
        assert "user_id" in data
        assert "level" in data

    def test_knowledge_search(self, client):
        resp = client.post('/api/knowledge/search', json={"query": "刷单"})
        assert resp.status_code == 200
        data = resp.get_json()
        assert "search_results" in data

    def test_leaderboard(self, client):
        resp = client.get('/api/user/leaderboard')
        assert resp.status_code == 200
        data = resp.get_json()
        assert "leaderboard" in data

    def test_daily_tasks(self, client):
        resp = client.get('/api/user/daily-tasks?user_id=test')
        assert resp.status_code == 200
        data = resp.get_json()
        assert "tasks" in data

    def test_clear_history(self, client):
        resp = client.post('/api/clear', json={})
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "ok"

    def test_laws(self, client):
        resp = client.get('/api/knowledge/laws')
        assert resp.status_code == 200
        data = resp.get_json()
        assert "laws" in data
        assert len(data["laws"]) > 0

    def test_knowledge_detail(self, client):
        resp = client.get('/api/knowledge/detail?type=刷单返利')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["id"] == "刷单返利"
