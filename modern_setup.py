#!/usr/bin/env python3
"""
X-SevenAI Modern Setup Script
Handles both local service setup and cloud configuration
"""

import os
import sys
import json
import subprocess
import platform
from pathlib import Path
from typing import Dict, List, Optional
import requests

class ServiceSetup:
    def __init__(self):
        self.project_root = Path(__file__).parent
        self.venv_path = self.project_root / ".venv"
        self.env_file = self.project_root / ".env"
        
    def check_system(self) -> Dict[str, bool]:
        """Check system capabilities"""
        checks = {
            'python': sys.version_info >= (3, 8),
            'pip': self.run_command(['pip', '--version'])[0] == 0,
            'brew': self.run_command(['brew', '--version'])[0] == 0,
            'docker': self.run_command(['docker', '--version'])[0] == 0,
            'node': self.run_command(['node', '--version'])[0] == 0,
        }
        return checks
    
    def run_command(self, cmd: List[str], cwd: Optional[str] = None) -> tuple:
        """Run shell command and return (exit_code, output)"""
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd)
            return result.returncode, result.stdout + result.stderr
        except FileNotFoundError:
            return 1, f"Command not found: {cmd[0]}"
    
    def setup_virtual_environment(self) -> bool:
        """Set up Python virtual environment"""
        print("🐍 Setting up Python virtual environment...")
        
        if not self.venv_path.exists():
            code, output = self.run_command([sys.executable, '-m', 'venv', str(self.venv_path)])
            if code != 0:
                print(f"❌ Failed to create venv: {output}")
                return False
        
        # Install dependencies
        pip_path = self.venv_path / "bin" / "pip"
        if platform.system() == "Windows":
            pip_path = self.venv_path / "Scripts" / "pip.exe"
        
        commands = [
            [str(pip_path), "install", "--upgrade", "pip"],
            [str(pip_path), "install", "-r", "requirements.txt"]
        ]
        
        for cmd in commands:
            code, output = self.run_command(cmd, cwd=str(self.project_root))
            if code != 0:
                print(f"❌ Command failed: {' '.join(cmd)}")
                print(output)
                return False
        
        print("✅ Virtual environment ready")
        return True
    
    def check_port(self, port: int) -> bool:
        """Check if port is available"""
        import socket
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                return s.connect_ex(('localhost', port)) != 0
        except:
            return False
    
    def setup_redis_local(self) -> bool:
        """Set up local Redis"""
        print("🔧 Setting up local Redis...")
        
        system = platform.system()
        
        if system == "Darwin":
            # macOS
            if self.run_command(['brew', '--version'])[0] == 0:
                self.run_command(['brew', 'install', 'redis'])
                self.run_command(['brew', 'services', 'start', 'redis'])
            else:
                print("❌ Homebrew not found. Please install Redis manually.")
                return False
        elif system == "Linux":
            # Ubuntu/Debian
            self.run_command(['sudo', 'apt-get', 'update'])
            self.run_command(['sudo', 'apt-get', 'install', '-y', 'redis-server'])
            self.run_command(['sudo', 'systemctl', 'start', 'redis'])
        
        # Wait for Redis to start
        import time
        for i in range(30):
            try:
                import redis
                r = redis.Redis(host='localhost', port=6379, decode_responses=True)
                if r.ping():
                    print("✅ Redis is ready")
                    return True
            except:
                pass
            time.sleep(1)
        
        print("❌ Redis failed to start")
        return False
    
    def setup_kafka_local(self) -> bool:
        """Set up local Kafka"""
        print("🔧 Setting up local Kafka...")
        
        system = platform.system()
        kafka_dir = self.project_root / "services_data" / "kafka"
        
        if system == "Darwin":
            if self.run_command(['brew', '--version'])[0] == 0:
                self.run_command(['brew', 'install', 'kafka'])
                self.run_command(['brew', 'services', 'start', 'zookeeper'])
                self.run_command(['brew', 'services', 'start', 'kafka'])
            else:
                print("❌ Homebrew not found")
                return False
        else:
            # Download and setup Kafka
            kafka_url = "https://downloads.apache.org/kafka/2.8.0/kafka_2.13-2.8.0.tgz"
            kafka_file = kafka_dir / "kafka.tgz"
            
            kafka_dir.mkdir(parents=True, exist_ok=True)
            
            if not (kafka_dir / "kafka_2.13-2.8.0").exists():
                print("📥 Downloading Kafka...")
                self.run_command(['curl', '-o', str(kafka_file), kafka_url])
                self.run_command(['tar', '-xzf', str(kafka_file), '-C', str(kafka_dir)])
            
            # Start Zookeeper and Kafka
            kafka_home = kafka_dir / "kafka_2.13-2.8.0"
            
            # Start Zookeeper
            self.run_command([
                'bash', '-c', 
                f'cd {kafka_home} && bin/zookeeper-server-start.sh -daemon config/zookeeper.properties'
            ])
            
            # Start Kafka
            self.run_command([
                'bash', '-c',
                f'cd {kafka_home} && bin/kafka-server-start.sh -daemon config/server.properties'
            ])
        
        print("✅ Kafka setup initiated")
        return True
    
    def setup_temporal_local(self) -> bool:
        """Set up local Temporal"""
        print("🔧 Setting up local Temporal...")
        
        system = platform.system()
        
        if system == "Darwin":
            if self.run_command(['brew', '--version'])[0] == 0:
                self.run_command(['brew', 'install', 'temporal'])
            else:
                # Install Temporal CLI
                self.run_command(['curl', '-sSf', 'https://temporal.download/cli.sh', '|', 'sh'])
        
        # Start Temporal development server
        temporal_dir = self.project_root / "services_data" / "temporal"
        temporal_dir.mkdir(parents=True, exist_ok=True)
        
        cmd = [
            'temporal', 'server', 'start-dev',
            '--port', '7233',
            '--ui-port', '8233',
            '--db-filename', str(temporal_dir / 'temporal.db')
        ]
        
        # Start in background
        subprocess.Popen(cmd, cwd=str(self.project_root))
        
        print("✅ Temporal development server started")
        return True
    
    def create_cloud_config(self) -> None:
        """Create cloud configuration template"""
        cloud_config = """# Cloud Services Configuration
# Copy these to your .env file

# Redis Cloud (Upstash)
REDIS_URL=redis://default:password@host:port

# Kafka Cloud (Confluent)
KAFKA_BOOTSTRAP_SERVERS=["your-cluster.kafka.confluent.cloud:9092"]
KAFKA_SECURITY_PROTOCOL=SASL_SSL
KAFKA_SASL_MECHANISM=PLAIN
KAFKA_SASL_USERNAME=your-api-key
KAFKA_SASL_PASSWORD=your-secret

# Temporal Cloud
TEMPORAL_HOST=your-namespace.tmprl.cloud:7233
TEMPORAL_NAMESPACE=your-namespace
TEMPORAL_TLS_CERT_PATH=./certs/client.pem
TEMPORAL_TLS_KEY_PATH=./certs/client.key

# PipeCat AI
PIPECAT_API_KEY=your-pipecat-key
"""
        
        with open(self.project_root / ".env.cloud", "w") as f:
            f.write(cloud_config)
        
        print("✅ Cloud configuration template created: .env.cloud")
    
    def verify_services(self) -> Dict[str, bool]:
        """Verify all services are running"""
        results = {}
        
        # Check Redis
        try:
            import redis
            r = redis.Redis(host='localhost', port=6379, decode_responses=True)
            results['redis'] = r.ping()
        except:
            results['redis'] = False
        
        # Check Kafka
        try:
            import socket
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                results['kafka'] = s.connect_ex(('localhost', 9092)) == 0
        except:
            results['kafka'] = False
        
        # Check Temporal
        try:
            import socket
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                results['temporal'] = s.connect_ex(('localhost', 7233)) == 0
        except:
            results['temporal'] = False
        
        return results
    
    def print_status(self, services: Dict[str, bool]) -> None:
        """Print service status"""
        print("\n📊 Service Status:")
        for service, status in services.items():
            emoji = "✅" if status else "❌"
            print(f"  {emoji} {service.title()}: {'Running' if status else 'Not running'}")
    
    def run_setup(self, mode: str = "local") -> bool:
        """Run complete setup"""
        print(f"🚀 Starting {mode} setup for X-SevenAI...")
        
        # Check system
        checks = self.check_system()
        print("\n📋 System Check:")
        for check, status in checks.items():
            emoji = "✅" if status else "❌"
            print(f"  {emoji} {check.title()}: {'Available' if status else 'Not available'}")
        
        # Setup virtual environment
        if not self.setup_virtual_environment():
            return False
        
        if mode == "local":
            # Setup local services
            self.setup_redis_local()
            self.setup_kafka_local()
            self.setup_temporal_local()
        
        # Create cloud config
        self.create_cloud_config()
        
        # Verify services
        services = self.verify_services()
        self.print_status(services)
        
        print("\n🎉 Setup complete!")
        print("\nNext steps:")
        print("1. For local services: ./setup_services.sh")
        print("2. For cloud services: copy .env.cloud to .env")
        print("3. Start app: source .venv/bin/activate && python -m app.main")
        
        return True

def main():
    setup = ServiceSetup()
    
    if len(sys.argv) > 1:
        mode = sys.argv[1]
    else:
        mode = "local"
    
    if mode not in ["local", "cloud"]:
        print("Usage: python modern_setup.py [local|cloud]")
        sys.exit(1)
    
    setup.run_setup(mode)

if __name__ == "__main__":
    main()
