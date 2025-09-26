#!/usr/bin/env python3
"""
X-SevenAI Verification Script
Tests all services and dependencies
"""

import os
import sys
import time
import socket
from pathlib import Path
import subprocess

class ServiceVerifier:
    def __init__(self):
        self.project_root = Path(__file__).parent
        
    def check_port(self, host: str, port: int, timeout: int = 5) -> bool:
        """Check if a port is accessible"""
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(timeout)
                return s.connect_ex((host, port)) == 0
        except:
            return False
    
    def check_redis(self) -> dict:
        """Check Redis connection"""
        try:
            import redis
            from app.config.settings import settings
            
            r = redis.from_url(settings.REDIS_URL)
            ping_result = r.ping()
            
            return {
                'status': '✅' if ping_result else '❌',
                'connected': ping_result,
                'url': settings.REDIS_URL,
                'message': 'Redis is ready' if ping_result else 'Redis connection failed'
            }
        except ImportError:
            return {'status': '❌', 'connected': False, 'message': 'Redis not installed'}
        except Exception as e:
            return {'status': '❌', 'connected': False, 'message': str(e)}
    
    def check_kafka(self) -> dict:
        """Check Kafka connection"""
        try:
            from app.config.settings import settings
            
            # Simple port check
            kafka_host = settings.KAFKA_BOOTSTRAP_SERVERS[0].split(':')[0]
            kafka_port = int(settings.KAFKA_BOOTSTRAP_SERVERS[0].split(':')[1])
            
            connected = self.check_port(kafka_host, kafka_port)
            
            return {
                'status': '✅' if connected else '❌',
                'connected': connected,
                'bootstrap_servers': settings.KAFKA_BOOTSTRAP_SERVERS,
                'message': 'Kafka is ready' if connected else 'Kafka connection failed'
            }
        except Exception as e:
            return {'status': '❌', 'connected': False, 'message': str(e)}
    
    def check_temporal(self) -> dict:
        """Check Temporal connection"""
        try:
            from app.config.settings import settings
            
            # Check if we can connect to Temporal
            temporal_host = 'localhost'
            temporal_port = 7233
            
            connected = self.check_port(temporal_host, temporal_port)
            
            return {
                'status': '✅' if connected else '❌',
                'connected': connected,
                'host': f'{temporal_host}:{temporal_port}',
                'message': 'Temporal is ready' if connected else 'Temporal connection failed'
            }
        except Exception as e:
            return {'status': '❌', 'connected': False, 'message': str(e)}
    
    def check_dependencies(self) -> dict:
        """Check Python dependencies"""
        critical_deps = [
            'fastapi', 'redis', 'temporalio', 'aiokafka', 'pipecat-ai',
            'supabase', 'langgraph', 'crewai', 'dspy-ai'
        ]
        
        results = {}
        for dep in critical_deps:
            try:
                __import__(dep.replace('-', '_'))
                results[dep] = '✅'
            except ImportError:
                results[dep] = '❌'
        
        return results
    
    def check_environment(self) -> dict:
        """Check environment variables"""
        from app.config.settings import settings
        
        critical_vars = [
            'OPENAI_API_KEY', 'GROQ_API_KEY', 'SUPABASE_URL', 'SUPABASE_KEY'
        ]
        
        results = {}
        for var in critical_vars:
            value = getattr(settings, var, None)
            results[var] = '✅' if value and len(str(value)) > 10 else '❌'
        
        return results
    
    def check_pipecat(self) -> dict:
        """Check PipeCat AI setup"""
        try:
            import pipecat_ai
            return {
                'status': '✅',
                'installed': True,
                'version': getattr(pipecat_ai, '__version__', 'unknown')
            }
        except ImportError:
            return {
                'status': '❌',
                'installed': False,
                'message': 'PipeCat AI not installed'
            }
    
    def run_all_checks(self) -> dict:
        """Run all verification checks"""
        print("🔍 Running X-SevenAI verification checks...")
        
        results = {
            'redis': self.check_redis(),
            'kafka': self.check_kafka(),
            'temporal': self.check_temporal(),
            'dependencies': self.check_dependencies(),
            'environment': self.check_environment(),
            'pipecat': self.check_pipecat()
        }
        
        return results
    
    def print_report(self, results: dict) -> None:
        """Print verification report"""
        print("\n" + "="*60)
        print("🎯 X-SevenAI Verification Report")
        print("="*60)
        
        # Service Status
        print("\n📡 Service Connections:")
        for service, result in results.items():
            if service in ['redis', 'kafka', 'temporal', 'pipecat']:
                print(f"  {result['status']} {service.title()}: {result.get('message', 'Unknown')}")
                if 'url' in result:
                    print(f"     URL: {result['url']}")
                if 'host' in result:
                    print(f"     Host: {result['host']}")
        
        # Dependencies
        print("\n📦 Python Dependencies:")
        for dep, status in results['dependencies'].items():
            print(f"  {status} {dep}")
        
        # Environment
        print("\n🔐 Environment Variables:")
        for var, status in results['environment'].items():
            print(f"  {status} {var}")
        
        # Summary
        all_services = [results.get(s, {}).get('connected', False) 
                       for s in ['redis', 'kafka', 'temporal']]
        all_deps = all(s == '✅' for s in results['dependencies'].values())
        all_env = all(s == '✅' for s in results['environment'].values())
        
        print("\n📊 Summary:")
        print(f"  Services Ready: {'✅' if all(all_services) else '❌'}")
        print(f"  Dependencies OK: {'✅' if all_deps else '❌'}")
        print(f"  Environment OK: {'✅' if all_env else '❌'}")
        
        if all(all_services) and all_deps and all_env:
            print("\n🎉 All systems ready! You can start X-SevenAI now.")
        else:
            print("\n⚠️  Some services need attention. Check the report above.")
            print("\nQuick fixes:")
            print("1. Run: python modern_setup.py local")
            print("2. Or use cloud services: python modern_setup.py cloud")
            print("3. Check .env file for missing API keys")

def main():
    verifier = ServiceVerifier()
    results = verifier.run_all_checks()
    verifier.print_report(results)

if __name__ == "__main__":
    main()
