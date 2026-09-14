"""Comprehensive smoke and unit tests for TVB Lead Agent 6-Gate validation & Adversarial Red-Teaming."""
from lead_agent import adversarial, config, query_generator, scraper, validator


def test_six_gate_evaluation():
    # 1. Perfectly qualifying record
    qualifying_input = {
        "company_name": "NexaPay",
        "description": "B2B cross-border payment platform for European merchants.",
        "industry_sector": "Fintech / Payments",
        "hq_country": "France",
        "has_significant_us_presence": "no",
        "is_tech_platform": "yes",
        "funding_or_revenue_usd_estimate": "3500000",
        "current_total_funding_usd": "3500000",
        "financial_type": "total_funding",
        "financial_date": "2024-05-18",
        "funding_or_revenue_evidence": "Closed $3.5M total funding in May 2024.",
        "contact_name": "Jean Dupont",
        "contact_title": "Founder & CEO",
        "contact_email": "jean.dupont@google.com",
        "source_url": "https://google.com",
    }
    qual, rej = validator.evaluate_record(qualifying_input)
    assert qual is not None, "Should pass all 6 gates"
    assert rej is None
    assert qual["qualification_status"] == "QUALIFIED"
    assert qual["financial_amount_usd"] == "$3,500,000"
    assert qual["technology_verified"] is True
    assert qual["email"] == "jean.dupont@google.com"
    assert qual["email_person_attributed"] is True
    assert qual["financial_date"] == "2024-05-18"

    # 2. Gate 2 Failure: Over $5M total funding cap (Omni / Dust / Koywe style)
    overfunded_input = dict(qualifying_input, current_total_funding_usd="15000000", funding_or_revenue_usd_estimate="15000000")
    qual, rej = validator.evaluate_record(overfunded_input)
    assert qual is None
    assert rej is not None
    assert rej["rejection_reason"] in ("TOTAL_FUNDING_ABOVE_LIMIT", "FUNDING_ABOVE_LIMIT")

    # 3. Gate 2 Failure: Under $1M minimum funding (Sanctifly / Fyorin style)
    underfunded_input = dict(qualifying_input, current_total_funding_usd="460000", funding_or_revenue_usd_estimate="460000")
    qual, rej = validator.evaluate_record(underfunded_input)
    assert qual is None
    assert rej is not None
    assert rej["rejection_reason"] == "FUNDING_BELOW_LIMIT"

    # 4. Gate 1 Failure: Acquired company (Langfuse / ClickHouse style)
    acquired_input = dict(qualifying_input, company_status="acquired")
    qual, rej = validator.evaluate_record(acquired_input)
    assert qual is None
    assert rej is not None
    assert rej["rejection_reason"] == "COMPANY_ACQUIRED_OR_CLOSED"

    # 5. Gate 4 Failure: US Presence (Kombai / San Francisco style)
    us_input = dict(qualifying_input, hq_country="United States")
    qual, rej = validator.evaluate_record(us_input)
    assert qual is None
    assert rej is not None
    assert rej["rejection_reason"] in ("US_PRESENCE_TOO_HIGH", "US_PRESENCE_UNKNOWN")

    # 6. Gate 6 Failure: Missing or Generic Email (Zero Guessing Policy)
    no_email_input = dict(qualifying_input, contact_email="", email="", allow_mx_pattern=False)
    qual, rej = validator.evaluate_record(no_email_input)
    assert qual is None
    assert rej is not None
    assert rej["rejection_reason"] == "EMAIL_NOT_VERIFIED"


def test_adversarial_break_testing():
    # Candidate exceeding $5M should be caught by adversarial checker
    bad_record = {
        "company_name": "BigScale",
        "financial_amount_usd": "$18,000,000",
        "current_total_funding_usd": "$18,000,000",
        "hq_country": "Germany",
    }
    passed, reason, exp = adversarial.verify_adversarial(bad_record)
    assert not passed
    assert reason in ("TOTAL_FUNDING_ABOVE_LIMIT", "FUNDING_ABOVE_LIMIT")

    # Candidate with US presence should be caught
    us_record = {
        "company_name": "USFlipCorp",
        "financial_amount_usd": "$3,000,000",
        "hq_country": "Delaware, USA",
    }
    passed, reason, exp = adversarial.verify_adversarial(us_record)
    assert not passed
    assert reason == "US_PRESENCE_TOO_HIGH"


def test_query_generation_and_negative_vectors():
    queries = query_generator.generate_queries(max_queries=10)
    assert len(queries) > 0
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


if __name__ == "__main__":
    test_six_gate_evaluation()
    test_adversarial_break_testing()
    test_query_generation_and_negative_vectors()
    test_scraper_firewall_detection()
    print("✅ All 6-Gate, Adversarial, and Validation smoke tests passed successfully!")
