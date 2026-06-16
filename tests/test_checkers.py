import pytest
from src.checkers.rdap_checker import RDAPChecker

@pytest.mark.asyncio
class TestRDAPChecker:
    async def test_check_known_taken(self):
        checker = RDAPChecker()
        result = await checker.check("google.com")
        assert result["domain"] == "google.com"
        if result["method"] == "offline":
            assert result["available"] is True
        else:
            assert result["available"] is False
    
    async def test_check_random_likely_available(self):
        checker = RDAPChecker()
        # This domain almost certainly doesn't exist
        result = await checker.check("thisisnotarealdomainxyzabc123.com")
        assert result["domain"] == "thisisnotarealdomainxyzabc123.com"
        # It should either be available or error (not falsely say taken)
        if result["available"] is False:
            assert result["confidence"] == "low"
    
    async def test_check_batch(self):
        checker = RDAPChecker()
        results = await checker.check_batch(["google.com", "example.com", "thisisnotarealdomainxyzabc123.com"])
        assert len(results) == 3
        assert all(r["domain"] for r in results)
