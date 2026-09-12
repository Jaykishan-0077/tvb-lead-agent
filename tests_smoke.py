"""Comprehensive smoke and unit tests for TVB Lead Agent validation & parsing."""
from lead_agent import config, query_generator, scraper, validator


def test_funding_parsing():
    # In-range tests ($1M to $5M)
    assert validator._funding_in_range({"funding_or_revenue_usd_estimate": "2500000"})
    assert validator._funding_in_range({"funding_or_revenue_usd_estimate": "$3.5M"})
    assert validator._funding_in_range({"funding_or_revenue_usd_estimate": "$1,000,000"})
    assert validator._funding_in_range({"funding_or_revenue_usd_estimate": "$5,000,000"})
    assert validator._funding_in_range({"funding_or_revenue_evidence": "Raised $2.8 million seed round."})

    # Out-of-range tests
    assert not validator._funding_in_range({"funding_or_revenue_usd_estimate": "250000"})
    assert not validator._funding_in_range({"funding_or_revenue_usd_estimate": "12000000"})
    assert not validator._funding_in_range({"funding_or_revenue_usd_estimate": ""})


def test_us_presence_filter():
    # Non-US countries
    assert not validator._looks_us({"hq_country": "India", "has_significant_us_presence": "no"})
    assert not validator._looks_us({"hq_country": "United Kingdom", "has_significant_us_presence": "no"})
    assert not validator._looks_us({"hq_country": "France", "has_significant_us_presence": "no"})

    # US-based entities
    assert validator._looks_us({"hq_country": "United States"})
    assert validator._looks_us({"hq_country": "USA"})
    assert validator._looks_us({"hq_country": "Delaware"})
    assert validator._looks_us({"hq_country": "France", "has_significant_us_presence": "yes"})
    assert validator._looks_us({"hq_country": "India", "has_significant_us_presence": True})


def test_email_validation():
    # Valid founder email formats on active domains
    assert validator.verify_email("alex@google.com", contact_name="Alex Smith")

    # Invalid / Disallowed formats
    assert not validator.verify_email("invalid-email-format", contact_name="Alex Smith")
    assert not validator.verify_email("info@linkedin.com", contact_name="Alex Smith")
    assert not validator.verify_email("support@techcrunch.com", contact_name="Alex Smith")
    assert not validator.verify_email("info@startup.com", contact_name="")  # generic without name


def test_query_generation_and_negative_vectors():
    queries = query_generator.generate_queries(max_queries=10)
    assert len(queries) > 0
    assert any("raised" in q.lower() or "funding" in q.lower() or "seed" in q.lower() for q in queries)
    assert any('-"Inc"' in q or '-"Delaware"' in q or '-"USA"' in q for q in queries)


def test_scraper_firewall_detection():
    assert scraper._is_firewall_or_error_page("Attention Required! | Cloudflare Ray ID: 12345")
    assert scraper._is_firewall_or_error_page("Please verify you are a human - DataDome")
    assert scraper._is_firewall_or_error_page("This domain is parked with ParkingCrew")
    assert not scraper._is_firewall_or_error_page(
        "Welcome to NexaPay, the leading European B2B payments platform. "
        "Founded in 2024 by Jane Doe, our team in London provides corporate cards "
        "and automated expense reconciliation for scale-ups across the UK and Germany."
    )


def test_domain_extraction():
    assert scraper.domain_of("https://www.example.com/about") == "example.com"
    assert scraper.domain_of("https://sub.domain.io/team") == "sub.domain.io"


def test_full_record_evaluation():
    valid_record = {
        "company_name": "TestCorp",
        "description": "Enterprise AI testing platform",
        "industry_sector": "Applied AI",
        "hq_country": "France",
        "has_significant_us_presence": "no",
        "is_tech_platform": "yes",
        "funding_or_revenue_usd_estimate": "3000000",
        "contact_name": "Alex Dupont",
        "contact_title": "Co-founder & CEO",
        "contact_email": "alex@google.com",
        "source_url": "https://google.com",
    }
    result = validator.evaluate_record(valid_record)
    assert result is not None
    assert result["company_name"] == "TestCorp"
    assert result["funding_or_revenue_usd_estimate"] == "$3,000,000"
    assert result["verified_email"] == "alex@google.com"


if __name__ == "__main__":
    test_funding_parsing()
    test_us_presence_filter()
    test_email_validation()
    test_query_generation_and_negative_vectors()
    test_scraper_firewall_detection()
    test_domain_extraction()
    test_full_record_evaluation()
    print("✅ All smoke and validation tests passed successfully!")
