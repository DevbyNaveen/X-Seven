#!/usr/bin/env python3
"""
Comprehensive Test Runner for X-Seven Backend
Tests all major components, services, and flows
"""

import asyncio
import logging
import sys
import time
import os
import json
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional, Set

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("comprehensive_test_log.txt")
    ]
)

logger = logging.getLogger("comprehensive-tests")

# Test categories
TEST_CATEGORIES = {
    "core_services": [
        "test_database.py",
        "test_redis.py",
        "test_kafka.py",
        "test_temporal.py"
    ],
    "ai_integration": [
        "test_dspy.py",
    ],
    "service_mesh": [
        "test_service_mesh.py"
    ],
    "api_endpoints": [
        "test_api_endpoints.py"
    ],
    "conversation_flows": [
        "test_conversation_flows.py"
    ],
    "end_to_end": [
        "test_end_to_end.py"
    ]
}


class ComprehensiveTestRunner:
    """Comprehensive test runner for X-Seven backend"""
    
    def __init__(self):
        self.results: Dict[str, Dict[str, Any]] = {}
        self.start_time = time.time()
        self.venv_path = Path(".venv")
        self.test_results_dir = Path("test_results")
        self.test_results_dir.mkdir(exist_ok=True)
        
        # Track which tests passed
        self.passed_tests: Set[str] = set()
        self.failed_tests: Set[str] = set()
    
    async def setup(self):
        """Set up test environment"""
        logger.info("Setting up test environment")
        
        # Check if virtual environment exists
        if not self.venv_path.exists():
            logger.error("Virtual environment not found at .venv")
            return False
        
        # Check Python version
        python_version = subprocess.run(
            [f"{self.venv_path}/bin/python", "--version"], 
            capture_output=True, 
            text=True
        ).stdout.strip()
        logger.info(f"Using {python_version}")
        
        # Verify dependencies
        requirements = subprocess.run(
            [f"{self.venv_path}/bin/pip", "freeze"], 
            capture_output=True, 
            text=True
        ).stdout
        logger.info(f"Found {len(requirements.splitlines())} installed packages")
        
        return True
    
    async def run_test(self, test_file: str, timeout: int = 120) -> Dict[str, Any]:
        """Run a single test script"""
        test_name = test_file.replace(".py", "")
        logger.info(f"Running test: {test_name}")
        
        # Skip if test file doesn't exist
        if not Path(test_file).exists():
            logger.warning(f"Test file not found: {test_file}")
            return {
                "name": test_name,
                "success": False,
                "error": "Test file not found",
                "duration": 0,
                "output": ""
            }
        
        start_time = time.time()
        command = f"source {self.venv_path}/bin/activate && python {test_file}"
        
        try:
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            try:
                stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout)
                stdout_str = stdout.decode("utf-8")
                stderr_str = stderr.decode("utf-8")
                
                duration = time.time() - start_time
                success = process.returncode == 0
                
                if success:
                    self.passed_tests.add(test_name)
                    logger.info(f"✅ {test_name} PASSED in {duration:.2f}s")
                else:
                    self.failed_tests.add(test_name)
                    logger.error(f"❌ {test_name} FAILED in {duration:.2f}s")
                
                return {
                    "name": test_name,
                    "success": success,
                    "return_code": process.returncode,
                    "duration": duration,
                    "stdout": stdout_str,
                    "stderr": stderr_str
                }
                
            except asyncio.TimeoutError:
                process.kill()
                self.failed_tests.add(test_name)
                logger.error(f"⏰ {test_name} TIMED OUT after {timeout}s")
                return {
                    "name": test_name,
                    "success": False,
                    "error": f"Test timed out after {timeout}s",
                    "duration": timeout,
                    "timed_out": True
                }
                
        except Exception as e:
            self.failed_tests.add(test_name)
            logger.error(f"❌ Error running {test_name}: {e}")
            return {
                "name": test_name,
                "success": False,
                "error": str(e),
                "duration": time.time() - start_time
            }
    
    async def run_category(self, category: str, tests: List[str]) -> Dict[str, Any]:
        """Run all tests in a category"""
        logger.info(f"Running test category: {category}")
        start_time = time.time()
        
        results = []
        for test_file in tests:
            result = await self.run_test(test_file)
            results.append(result)
        
        duration = time.time() - start_time
        success_count = sum(1 for r in results if r.get("success", False))
        
        logger.info(f"Category {category}: {success_count}/{len(tests)} tests passed in {duration:.2f}s")
        
        return {
            "category": category,
            "success_count": success_count,
            "total_tests": len(tests),
            "success_rate": success_count / max(len(tests), 1),
            "duration": duration,
            "test_results": results
        }
    
    async def run_all_categories(self):
        """Run all test categories"""
        logger.info("Running all test categories")
        
        for category, tests in TEST_CATEGORIES.items():
            result = await self.run_category(category, tests)
            self.results[category] = result
    
    def generate_report(self) -> str:
        """Generate comprehensive test report"""
        total_duration = time.time() - self.start_time
        
        all_tests = sum(len(tests) for tests in TEST_CATEGORIES.values())
        passed_tests = len(self.passed_tests)
        failed_tests = len(self.failed_tests)
        
        report_lines = []
        report_lines.append("=" * 80)
        report_lines.append("X-SEVEN COMPREHENSIVE TEST REPORT")
        report_lines.append("=" * 80)
        report_lines.append(f"Generated: {datetime.now().isoformat()}")
        report_lines.append(f"Total duration: {total_duration:.2f}s")
        report_lines.append("")
        
        # Summary
        report_lines.append("SUMMARY:")
        report_lines.append(f"Test categories: {len(TEST_CATEGORIES)}")
        report_lines.append(f"Total tests: {all_tests}")
        report_lines.append(f"Tests passed: {passed_tests}")
        report_lines.append(f"Tests failed: {failed_tests}")
        report_lines.append(f"Success rate: {passed_tests / max(all_tests, 1) * 100:.1f}%")
        report_lines.append("")
        
        # Category results
        report_lines.append("CATEGORY RESULTS:")
        for category, result in self.results.items():
            status = "✅ PASSED" if result["success_rate"] == 1.0 else "❌ FAILED"
            report_lines.append(f"{status} {category}: {result['success_count']}/{result['total_tests']} tests in {result['duration']:.2f}s")
        report_lines.append("")
        
        # Failure details
        if self.failed_tests:
            report_lines.append("FAILED TESTS:")
            for category, result in self.results.items():
                for test in result["test_results"]:
                    if not test.get("success", False):
                        report_lines.append(f"❌ {test['name']}:")
                        if "error" in test:
                            report_lines.append(f"   Error: {test['error']}")
                        if "stderr" in test and test["stderr"].strip():
                            report_lines.append(f"   Details: {test['stderr'].splitlines()[0]}")
            report_lines.append("")
        
        # Recommendations
        report_lines.append("RECOMMENDATIONS:")
        
        if failed_tests > 0:
            report_lines.append("- Fix failed tests before deploying to production")
            
            # Service-specific recommendations
            service_failures = {
                "database": "test_database" in self.failed_tests,
                "redis": "test_redis" in self.failed_tests,
                "kafka": "test_kafka" in self.failed_tests,
                "temporal": "test_temporal" in self.failed_tests,
                "dspy": "test_dspy" in self.failed_tests,
                "service_mesh": "test_service_mesh" in self.failed_tests,
            }
            
            for service, failed in service_failures.items():
                if failed:
                    report_lines.append(f"- Check {service} configuration and connectivity")
        else:
            report_lines.append("- All tests passed! The system is ready for production")
            report_lines.append("- Consider adding performance tests under load")
            report_lines.append("- Set up monitoring and alerting")
        
        report_lines.append("")
        report_lines.append("=" * 80)
        
        return "\n".join(report_lines)
    
    def save_report(self, report: str):
        """Save test report to file"""
        report_file = "COMPREHENSIVE_TEST_REPORT.md"
        with open(report_file, "w") as f:
            f.write(report)
        
        logger.info(f"Report saved to {report_file}")
    
    def save_detailed_results(self):
        """Save detailed test results to JSON file"""
        results_file = self.test_results_dir / "detailed_results.json"
        
        # Convert sets to lists for JSON serialization
        serializable_results = {
            "categories": self.results,
            "passed_tests": list(self.passed_tests),
            "failed_tests": list(self.failed_tests),
            "timestamp": datetime.now().isoformat(),
            "total_duration": time.time() - self.start_time
        }
        
        with open(results_file, "w") as f:
            json.dump(serializable_results, f, indent=2, default=str)
        
        logger.info(f"Detailed results saved to {results_file}")


async def main():
    """Main function"""
    logger.info("=" * 80)
    logger.info("X-SEVEN COMPREHENSIVE TEST RUNNER")
    logger.info("=" * 80)
    
    runner = ComprehensiveTestRunner()
    
    # Setup
    setup_success = await runner.setup()
    if not setup_success:
        logger.error("Setup failed, cannot continue with tests")
        sys.exit(1)
    
    # Run all tests
    await runner.run_all_categories()
    
    # Generate report
    report = runner.generate_report()
    print("\n" + report)
    
    # Save results
    runner.save_report(report)
    runner.save_detailed_results()
    
    # Exit with appropriate code
    if runner.failed_tests:
        sys.exit(1)
    else:
        sys.exit(0)


if __name__ == "__main__":
    asyncio.run(main())
