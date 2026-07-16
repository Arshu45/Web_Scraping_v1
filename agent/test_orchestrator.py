# agent/test_orchestrator.py

import logging
import sys
import os
from unittest.mock import patch

# Ensure the root of the project is in the python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent import build_agent_graph, AgentState, ValidationReport
from agent.models import SiteAnalysis

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create a mock explore_site function that doesn't hit external APIs
def get_mock_site_analysis(url, brand):
    return SiteAnalysis(
        url=url,
        brand=brand,
        screenshot_path="mock_screenshot.png",
        dom_html="<html><body>Mock DOM</body></html>",
        extraction_strategy="text",
        anti_bot_signals={},
        anti_bot_risk="low"
    )

@patch('agent.exploration_agent.explore_site', side_effect=get_mock_site_analysis)
def test_auto_approve(mock_explore):
    logger.info("--- Testing Auto-Approve Route (Score: 95, no violations) ---")
    graph = build_agent_graph()
    
    state = AgentState(
        url="https://example.com",
        brand="Test Brand",
        requirements="Test requirements"
    )
    
    state.validation_report = ValidationReport(
        brand="Test Brand",
        scraper_ran=True,
        offers_extracted=10,
        schema_valid=True,
        confidence_score=95,
        recommendation="auto_approve",
        sandbox_violations=[]
    )
    
    final_state = graph.invoke(state)
    logger.info("Final status: %s", final_state["status"])
    assert final_state["status"] == "registered", f"Expected 'registered', got {final_state['status']}"
    logger.info("✓ Auto-approve test passed!")

@patch('agent.exploration_agent.explore_site', side_effect=get_mock_site_analysis)
def test_pending_review(mock_explore):
    logger.info("--- Testing Pending Review Route (Score: 80, no violations) ---")
    graph = build_agent_graph()
    
    state = AgentState(
        url="https://example.com",
        brand="Test Brand",
        requirements="Test requirements"
    )
    
    state.validation_report = ValidationReport(
        brand="Test Brand",
        scraper_ran=True,
        offers_extracted=5,
        schema_valid=True,
        confidence_score=80,
        recommendation="pending",
        sandbox_violations=[]
    )
    
    final_state = graph.invoke(state)
    logger.info("Final status: %s", final_state["status"])
    assert final_state["status"] == "validation", f"Expected 'validation', got {final_state['status']}"
    logger.info("✓ Pending review test passed!")

@patch('agent.exploration_agent.explore_site', side_effect=get_mock_site_analysis)
def test_reject_low_score(mock_explore):
    logger.info("--- Testing Reject Route (Score: 50, no violations) ---")
    graph = build_agent_graph()
    
    state = AgentState(
        url="https://example.com",
        brand="Test Brand",
        requirements="Test requirements"
    )
    
    state.validation_report = ValidationReport(
        brand="Test Brand",
        scraper_ran=True,
        offers_extracted=2,
        schema_valid=False,
        confidence_score=50,
        recommendation="reject",
        sandbox_violations=[]
    )
    
    final_state = graph.invoke(state)
    logger.info("Final status: %s", final_state["status"])
    assert final_state["status"] == "validation", f"Expected 'validation', got {final_state['status']}"
    logger.info("✓ Reject low score test passed!")

@patch('agent.exploration_agent.explore_site', side_effect=get_mock_site_analysis)
def test_reject_sandbox_violations(mock_explore):
    logger.info("--- Testing Reject Route (Score: 95, with sandbox violations) ---")
    graph = build_agent_graph()
    
    state = AgentState(
        url="https://example.com",
        brand="Test Brand",
        requirements="Test requirements"
    )
    
    state.validation_report = ValidationReport(
        brand="Test Brand",
        scraper_ran=True,
        offers_extracted=10,
        schema_valid=True,
        confidence_score=95,
        recommendation="reject",
        sandbox_violations=["attempted_write_to_etc"]
    )
    
    final_state = graph.invoke(state)
    logger.info("Final status: %s", final_state["status"])
    assert final_state["status"] == "validation", f"Expected 'validation', got {final_state['status']}"
    logger.info("✓ Reject sandbox violations test passed!")

if __name__ == "__main__":
    try:
        test_auto_approve()
        test_pending_review()
        test_reject_low_score()
        test_reject_sandbox_violations()
        logger.info("\n🎉 All orchestrator routing tests passed successfully!")
    except AssertionError as e:
        logger.error("❌ Test failed: %s", e)
        sys.exit(1)
