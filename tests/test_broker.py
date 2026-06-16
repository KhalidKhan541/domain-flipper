import pytest
from src.analyzers.broker import BrokerAnalyzer
from src.coordinators.broker import BrokerCoordinator


@pytest.mark.asyncio
class TestBrokerAnalyzer:
    async def test_analyze_returns_required_fields(self):
        analyzer = BrokerAnalyzer()
        result = await analyzer.analyze("aifinancehub.com", "finance")
        assert result["domain_name"] == "aifinancehub.com"
        assert "marketplace" in result
        assert "buyer_leads" in result
        assert "estimated_value" in result
        assert "commission" in result
        assert "broker_score" in result
        assert "broker_grade" in result

    async def test_buyer_leads_for_ai_niche(self):
        analyzer = BrokerAnalyzer()
        result = await analyzer.analyze("neurallabs.io", "ai")
        leads = result["buyer_leads"]
        assert leads["total_leads"] >= 3
        assert len(leads["leads"]) > 0
        lead_names = [l["company"].lower() for l in leads["leads"]]
        assert any("openai" in n or "anthropic" in n or "hugging" in n for n in lead_names)

    async def test_buyer_leads_for_health_niche(self):
        analyzer = BrokerAnalyzer()
        result = await analyzer.analyze("dailywellnesshub.com", "health")
        leads = result["buyer_leads"]
        assert leads["total_leads"] >= 3
        lead_names = [l["company"].lower() for l in leads["leads"]]
        assert any("teladoc" in n or "noom" in n or "calm" in n for n in lead_names)

    async def test_marketplace_check(self):
        analyzer = BrokerAnalyzer()
        result = await analyzer.analyze("taskly.app", "productivity")
        marketplace = result["marketplace"]
        assert "is_listed" in marketplace
        assert "listings" in marketplace
        assert "score" in marketplace

    async def test_estimated_value_range(self):
        analyzer = BrokerAnalyzer()
        result = await analyzer.analyze("short.com", "general")
        assert result["estimated_value"] >= 50

    async def test_estimated_value_premium_for_com(self):
        analyzer = BrokerAnalyzer()
        com = await analyzer.analyze("premiumai.com", "ai")
        io = await analyzer.analyze("premiumai.io", "ai")
        assert com["estimated_value"] >= io["estimated_value"]

    async def test_commission_is_15_percent(self):
        analyzer = BrokerAnalyzer()
        result = await analyzer.analyze("cloudpulse.io", "saas")
        comm = result["commission"]
        assert comm["rate"] == 0.15
        expected = round(result["estimated_value"] * 0.15)
        assert comm["amount"] == expected

    async def test_broker_grade_is_valid(self):
        analyzer = BrokerAnalyzer()
        result = await analyzer.analyze("testdomainxyzabc.com", "general")
        assert result["broker_grade"] in ("Hot Lead", "Warm", "Lukewarm", "Cold")

    async def test_broker_score_range(self):
        analyzer = BrokerAnalyzer()
        result = await analyzer.analyze("aifinancehub.com", "finance")
        assert 0 <= result["broker_score"] <= 100


@pytest.mark.asyncio
class TestBrokerCoordinator:
    async def test_discover_returns_domains(self):
        coordinator = BrokerCoordinator()
        domains = await coordinator.discover(max_domains=10)
        assert len(domains) > 0
        for d in domains:
            assert "domain_name" in d
            assert "." in d["domain_name"]

    async def test_analyze_all_adds_broker_fields(self):
        coordinator = BrokerCoordinator()
        domains = await coordinator.discover(max_domains=5)
        results = await coordinator.analyze_all(domains)
        for r in results:
            assert "broker_score" in r
            assert "broker_grade" in r
            assert "estimated_value" in r
            assert "commission" in r
            assert "buyer_leads" in r
            assert "marketplace" in r
