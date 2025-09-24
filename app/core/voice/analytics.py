"""
Voice Analytics and Monitoring System

Comprehensive analytics and monitoring for PipeCat voice integration
with performance metrics, quality tracking, and business intelligence.
"""

import asyncio
import logging
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
import json
import statistics

logger = logging.getLogger(__name__)


class VoiceMetricType(str, Enum):
    """Types of voice metrics."""
    CALL_VOLUME = "call_volume"
    RESPONSE_TIME = "response_time"
    AUDIO_QUALITY = "audio_quality"
    INTENT_ACCURACY = "intent_accuracy"
    USER_SATISFACTION = "user_satisfaction"
    ERROR_RATE = "error_rate"
    CONVERSATION_LENGTH = "conversation_length"
    DSPY_PERFORMANCE = "dspy_performance"


@dataclass
class VoiceMetric:
    """Individual voice metric data point."""
    metric_type: VoiceMetricType
    value: float
    timestamp: datetime
    session_id: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)


@dataclass
class VoiceAnalyticsReport:
    """Voice analytics report."""
    report_id: str
    time_period: Tuple[datetime, datetime]
    total_calls: int
    successful_calls: int
    failed_calls: int
    average_response_time: float
    average_call_duration: float
    average_audio_quality: float
    intent_accuracy_rate: float
    user_satisfaction_score: float
    error_rate: float
    peak_hours: List[int]
    top_intents: List[Dict[str, Any]]
    dspy_optimization_impact: Dict[str, Any]
    recommendations: List[str]
    generated_at: datetime


class VoiceAnalyticsCollector:
    """Collects and stores voice analytics data."""
    
    def __init__(self):
        self.metrics: List[VoiceMetric] = []
        self.session_data: Dict[str, Dict[str, Any]] = {}
        self.real_time_stats: Dict[str, Any] = {}
        self.is_collecting = False
        
        logger.info("VoiceAnalyticsCollector initialized")
    
    async def start_collection(self):
        """Start analytics collection."""
        self.is_collecting = True
        logger.info("Voice analytics collection started")
    
    async def stop_collection(self):
        """Stop analytics collection."""
        self.is_collecting = False
        logger.info("Voice analytics collection stopped")
    
    async def record_metric(self, metric: VoiceMetric):
        """Record a voice metric."""
        if not self.is_collecting:
            return
        
        try:
            self.metrics.append(metric)
            await self._update_real_time_stats(metric)
            
            # Limit metrics storage to prevent memory issues
            if len(self.metrics) > 10000:
                self.metrics = self.metrics[-5000:]  # Keep last 5000 metrics
            
            logger.debug(f"Recorded metric: {metric.metric_type} = {metric.value}")
            
        except Exception as e:
            logger.error(f"Error recording metric: {e}")
    
    async def record_call_start(self, session_id: str, call_data: Dict[str, Any]):
        """Record the start of a voice call."""
        try:
            self.session_data[session_id] = {
                "start_time": datetime.now(),
                "call_data": call_data,
                "metrics": [],
                "status": "active"
            }
            
            # Record call volume metric
            await self.record_metric(VoiceMetric(
                metric_type=VoiceMetricType.CALL_VOLUME,
                value=1.0,
                timestamp=datetime.now(),
                session_id=session_id,
                metadata=call_data
            ))
            
        except Exception as e:
            logger.error(f"Error recording call start: {e}")
    
    async def record_call_end(self, session_id: str, success: bool, error: Optional[str] = None):
        """Record the end of a voice call."""
        try:
            if session_id not in self.session_data:
                logger.warning(f"No session data found for {session_id}")
                return
            
            session = self.session_data[session_id]
            end_time = datetime.now()
            duration = (end_time - session["start_time"]).total_seconds()
            
            # Update session
            session["end_time"] = end_time
            session["duration"] = duration
            session["success"] = success
            session["error"] = error
            session["status"] = "completed"
            
            # Record metrics
            await self.record_metric(VoiceMetric(
                metric_type=VoiceMetricType.CONVERSATION_LENGTH,
                value=duration,
                timestamp=end_time,
                session_id=session_id,
                metadata={"success": success, "error": error}
            ))
            
            if not success and error:
                await self.record_metric(VoiceMetric(
                    metric_type=VoiceMetricType.ERROR_RATE,
                    value=1.0,
                    timestamp=end_time,
                    session_id=session_id,
                    metadata={"error": error}
                ))
            
        except Exception as e:
            logger.error(f"Error recording call end: {e}")
    
    async def record_response_time(self, session_id: str, response_time_ms: float):
        """Record response time for a voice interaction."""
        await self.record_metric(VoiceMetric(
            metric_type=VoiceMetricType.RESPONSE_TIME,
            value=response_time_ms,
            timestamp=datetime.now(),
            session_id=session_id
        ))
    
    async def record_audio_quality(self, session_id: str, quality_score: float):
        """Record audio quality score."""
        await self.record_metric(VoiceMetric(
            metric_type=VoiceMetricType.AUDIO_QUALITY,
            value=quality_score,
            timestamp=datetime.now(),
            session_id=session_id
        ))
    
    async def record_intent_accuracy(self, session_id: str, predicted_intent: str, 
                                   actual_intent: str, confidence: float):
        """Record intent detection accuracy."""
        accuracy = 1.0 if predicted_intent == actual_intent else 0.0
        
        await self.record_metric(VoiceMetric(
            metric_type=VoiceMetricType.INTENT_ACCURACY,
            value=accuracy,
            timestamp=datetime.now(),
            session_id=session_id,
            metadata={
                "predicted_intent": predicted_intent,
                "actual_intent": actual_intent,
                "confidence": confidence
            }
        ))
    
    async def record_user_satisfaction(self, session_id: str, satisfaction_score: float):
        """Record user satisfaction score (1-5)."""
        await self.record_metric(VoiceMetric(
            metric_type=VoiceMetricType.USER_SATISFACTION,
            value=satisfaction_score,
            timestamp=datetime.now(),
            session_id=session_id
        ))
    
    async def record_dspy_performance(self, session_id: str, module_name: str, 
                                    performance_data: Dict[str, Any]):
        """Record DSPy module performance."""
        await self.record_metric(VoiceMetric(
            metric_type=VoiceMetricType.DSPY_PERFORMANCE,
            value=performance_data.get("score", 0.0),
            timestamp=datetime.now(),
            session_id=session_id,
            metadata={
                "module_name": module_name,
                "performance_data": performance_data
            }
        ))
    
    async def _update_real_time_stats(self, metric: VoiceMetric):
        """Update real-time statistics."""
        try:
            metric_type = metric.metric_type.value
            
            if metric_type not in self.real_time_stats:
                self.real_time_stats[metric_type] = {
                    "count": 0,
                    "sum": 0.0,
                    "min": float('inf'),
                    "max": float('-inf'),
                    "recent_values": []
                }
            
            stats = self.real_time_stats[metric_type]
            stats["count"] += 1
            stats["sum"] += metric.value
            stats["min"] = min(stats["min"], metric.value)
            stats["max"] = max(stats["max"], metric.value)
            
            # Keep recent values for trend analysis
            stats["recent_values"].append(metric.value)
            if len(stats["recent_values"]) > 100:
                stats["recent_values"] = stats["recent_values"][-50:]
            
        except Exception as e:
            logger.error(f"Error updating real-time stats: {e}")
    
    def get_real_time_stats(self) -> Dict[str, Any]:
        """Get current real-time statistics."""
        stats = {}
        
        for metric_type, data in self.real_time_stats.items():
            if data["count"] > 0:
                stats[metric_type] = {
                    "count": data["count"],
                    "average": data["sum"] / data["count"],
                    "min": data["min"],
                    "max": data["max"],
                    "recent_trend": self._calculate_trend(data["recent_values"])
                }
        
        return stats
    
    def _calculate_trend(self, values: List[float]) -> str:
        """Calculate trend direction from recent values."""
        if len(values) < 5:
            return "insufficient_data"
        
        recent = values[-5:]
        earlier = values[-10:-5] if len(values) >= 10 else values[:-5]
        
        if not earlier:
            return "insufficient_data"
        
        recent_avg = statistics.mean(recent)
        earlier_avg = statistics.mean(earlier)
        
        if recent_avg > earlier_avg * 1.05:
            return "increasing"
        elif recent_avg < earlier_avg * 0.95:
            return "decreasing"
        else:
            return "stable"
    
    def get_session_metrics(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get metrics for a specific session."""
        if session_id not in self.session_data:
            return None
        
        session = self.session_data[session_id]
        session_metrics = [m for m in self.metrics if m.session_id == session_id]
        
        return {
            "session_data": session,
            "metrics_count": len(session_metrics),
            "metrics": [
                {
                    "type": m.metric_type.value,
                    "value": m.value,
                    "timestamp": m.timestamp.isoformat(),
                    "metadata": m.metadata
                }
                for m in session_metrics
            ]
        }


class VoiceAnalyticsReporter:
    """Generates voice analytics reports."""
    
    def __init__(self, collector: VoiceAnalyticsCollector):
        self.collector = collector
        logger.info("VoiceAnalyticsReporter initialized")
    
    async def generate_report(self, 
                            start_time: datetime, 
                            end_time: datetime) -> VoiceAnalyticsReport:
        """Generate comprehensive analytics report."""
        try:
            # Filter metrics by time period
            period_metrics = [
                m for m in self.collector.metrics
                if start_time <= m.timestamp <= end_time
            ]
            
            # Calculate basic statistics
            total_calls = len(set(m.session_id for m in period_metrics 
                                if m.metric_type == VoiceMetricType.CALL_VOLUME))
            
            successful_calls = len([
                s for s in self.collector.session_data.values()
                if s.get("success", False) and 
                start_time <= s.get("start_time", datetime.min) <= end_time
            ])
            
            failed_calls = total_calls - successful_calls
            
            # Calculate averages
            response_times = [m.value for m in period_metrics 
                            if m.metric_type == VoiceMetricType.RESPONSE_TIME]
            avg_response_time = statistics.mean(response_times) if response_times else 0.0
            
            call_durations = [m.value for m in period_metrics 
                            if m.metric_type == VoiceMetricType.CONVERSATION_LENGTH]
            avg_call_duration = statistics.mean(call_durations) if call_durations else 0.0
            
            audio_qualities = [m.value for m in period_metrics 
                             if m.metric_type == VoiceMetricType.AUDIO_QUALITY]
            avg_audio_quality = statistics.mean(audio_qualities) if audio_qualities else 0.0
            
            intent_accuracies = [m.value for m in period_metrics 
                               if m.metric_type == VoiceMetricType.INTENT_ACCURACY]
            intent_accuracy_rate = statistics.mean(intent_accuracies) if intent_accuracies else 0.0
            
            satisfaction_scores = [m.value for m in period_metrics 
                                 if m.metric_type == VoiceMetricType.USER_SATISFACTION]
            user_satisfaction = statistics.mean(satisfaction_scores) if satisfaction_scores else 0.0
            
            error_count = len([m for m in period_metrics 
                             if m.metric_type == VoiceMetricType.ERROR_RATE])
            error_rate = error_count / max(total_calls, 1)
            
            # Analyze peak hours
            peak_hours = self._analyze_peak_hours(period_metrics)
            
            # Analyze top intents
            top_intents = self._analyze_top_intents(period_metrics)
            
            # Analyze DSPy performance
            dspy_impact = self._analyze_dspy_performance(period_metrics)
            
            # Generate recommendations
            recommendations = self._generate_recommendations(
                total_calls, error_rate, avg_response_time, intent_accuracy_rate
            )
            
            report = VoiceAnalyticsReport(
                report_id=f"voice_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                time_period=(start_time, end_time),
                total_calls=total_calls,
                successful_calls=successful_calls,
                failed_calls=failed_calls,
                average_response_time=avg_response_time,
                average_call_duration=avg_call_duration,
                average_audio_quality=avg_audio_quality,
                intent_accuracy_rate=intent_accuracy_rate,
                user_satisfaction_score=user_satisfaction,
                error_rate=error_rate,
                peak_hours=peak_hours,
                top_intents=top_intents,
                dspy_optimization_impact=dspy_impact,
                recommendations=recommendations,
                generated_at=datetime.now()
            )
            
            logger.info(f"Generated voice analytics report: {report.report_id}")
            return report
            
        except Exception as e:
            logger.error(f"Error generating analytics report: {e}")
            raise
    
    def _analyze_peak_hours(self, metrics: List[VoiceMetric]) -> List[int]:
        """Analyze peak calling hours."""
        try:
            hour_counts = {}
            
            for metric in metrics:
                if metric.metric_type == VoiceMetricType.CALL_VOLUME:
                    hour = metric.timestamp.hour
                    hour_counts[hour] = hour_counts.get(hour, 0) + 1
            
            # Return top 3 peak hours
            sorted_hours = sorted(hour_counts.items(), key=lambda x: x[1], reverse=True)
            return [hour for hour, count in sorted_hours[:3]]
            
        except Exception as e:
            logger.error(f"Error analyzing peak hours: {e}")
            return []
    
    def _analyze_top_intents(self, metrics: List[VoiceMetric]) -> List[Dict[str, Any]]:
        """Analyze most common intents."""
        try:
            intent_counts = {}
            
            for metric in metrics:
                if (metric.metric_type == VoiceMetricType.INTENT_ACCURACY and 
                    "predicted_intent" in metric.metadata):
                    intent = metric.metadata["predicted_intent"]
                    intent_counts[intent] = intent_counts.get(intent, 0) + 1
            
            # Return top 5 intents
            sorted_intents = sorted(intent_counts.items(), key=lambda x: x[1], reverse=True)
            return [
                {"intent": intent, "count": count, "percentage": count / sum(intent_counts.values()) * 100}
                for intent, count in sorted_intents[:5]
            ]
            
        except Exception as e:
            logger.error(f"Error analyzing top intents: {e}")
            return []
    
    def _analyze_dspy_performance(self, metrics: List[VoiceMetric]) -> Dict[str, Any]:
        """Analyze DSPy optimization performance."""
        try:
            dspy_metrics = [m for m in metrics if m.metric_type == VoiceMetricType.DSPY_PERFORMANCE]
            
            if not dspy_metrics:
                return {"available": False, "message": "No DSPy performance data"}
            
            module_performance = {}
            for metric in dspy_metrics:
                module_name = metric.metadata.get("module_name", "unknown")
                if module_name not in module_performance:
                    module_performance[module_name] = []
                module_performance[module_name].append(metric.value)
            
            # Calculate averages for each module
            module_averages = {
                module: statistics.mean(scores)
                for module, scores in module_performance.items()
            }
            
            return {
                "available": True,
                "modules_analyzed": len(module_performance),
                "module_performance": module_averages,
                "overall_average": statistics.mean([
                    score for scores in module_performance.values() for score in scores
                ]) if module_performance else 0.0
            }
            
        except Exception as e:
            logger.error(f"Error analyzing DSPy performance: {e}")
            return {"available": False, "error": str(e)}
    
    def _generate_recommendations(self, total_calls: int, error_rate: float, 
                                avg_response_time: float, intent_accuracy: float) -> List[str]:
        """Generate recommendations based on analytics."""
        recommendations = []
        
        try:
            if total_calls < 10:
                recommendations.append("Consider increasing voice system promotion to drive more usage")
            
            if error_rate > 0.1:
                recommendations.append(f"High error rate ({error_rate:.1%}) - investigate common failure points")
            
            if avg_response_time > 2000:  # 2 seconds
                recommendations.append("Response time is high - consider optimizing voice processing pipeline")
            
            if intent_accuracy < 0.8:
                recommendations.append("Intent accuracy is low - consider retraining DSPy intent detection module")
            
            if intent_accuracy > 0.95:
                recommendations.append("Excellent intent accuracy - consider expanding to more complex use cases")
            
            if avg_response_time < 500:  # Very fast
                recommendations.append("Excellent response times - system is performing well")
            
            if not recommendations:
                recommendations.append("System is performing well - continue monitoring")
            
        except Exception as e:
            logger.error(f"Error generating recommendations: {e}")
            recommendations.append("Unable to generate recommendations due to analysis error")
        
        return recommendations


# Global analytics instances
_analytics_collector: Optional[VoiceAnalyticsCollector] = None
_analytics_reporter: Optional[VoiceAnalyticsReporter] = None


def get_voice_analytics_collector() -> VoiceAnalyticsCollector:
    """Get the global voice analytics collector."""
    global _analytics_collector
    if _analytics_collector is None:
        _analytics_collector = VoiceAnalyticsCollector()
    return _analytics_collector


def get_voice_analytics_reporter() -> VoiceAnalyticsReporter:
    """Get the global voice analytics reporter."""
    global _analytics_reporter
    if _analytics_reporter is None:
        collector = get_voice_analytics_collector()
        _analytics_reporter = VoiceAnalyticsReporter(collector)
    return _analytics_reporter


async def initialize_voice_analytics() -> bool:
    """Initialize voice analytics system."""
    try:
        collector = get_voice_analytics_collector()
        await collector.start_collection()
        
        logger.info("Voice analytics system initialized")
        return True
        
    except Exception as e:
        logger.error(f"Error initializing voice analytics: {e}")
        return False


async def cleanup_voice_analytics() -> bool:
    """Cleanup voice analytics system."""
    try:
        collector = get_voice_analytics_collector()
        await collector.stop_collection()
        
        logger.info("Voice analytics system cleaned up")
        return True
        
    except Exception as e:
        logger.error(f"Error cleaning up voice analytics: {e}")
        return False
