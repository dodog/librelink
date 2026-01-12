"""Enhanced trend calculation for LibreLink integration."""
from __future__ import annotations
import logging
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any, Optional

_LOGGER = logging.getLogger(__name__)

class TrendCalculator:
    """Calculate glucose trend based on historical measurements."""

    def __init__(self, max_history: int = 30):
        """Initialize trend calculator.

        Args:
            max_history: Maximum number of historical measurements to keep
        """
        self.max_history = max_history
        self.history: List[Dict[str, Any]] = []
        self._last_added_timestamp = None  # Track last timestamp to avoid duplicates

    def add_measurement(self, measurement: Dict[str, Any]) -> None:
        """Add a new glucose measurement to history, skipping duplicates."""
        # Ensure we have required fields
        if not all(key in measurement for key in ["Timestamp", "Value", "TrendArrow"]):
            return

        # Convert timestamp
        timestamp = measurement["Timestamp"]
        parsed_time = None
        try:
            if isinstance(timestamp, str):
                # Handle string timestamp
                if timestamp.endswith("Z"):
                    timestamp = timestamp[:-1] + "+00:00"
                parsed_time = datetime.fromisoformat(timestamp)
            elif isinstance(timestamp, datetime):
                parsed_time = timestamp
            else:
                return

            # Ensure timezone aware
            if parsed_time.tzinfo is None:
                parsed_time = parsed_time.replace(tzinfo=timezone.utc)

            # Skip if this exact timestamp was just added
            if self._last_added_timestamp == parsed_time:
                _LOGGER.debug(
                    "Skipping duplicate measurement at time %s (value: %s)",
                    parsed_time, measurement.get("Value")
                )
                return

        except Exception:
            _LOGGER.debug("Error parsing timestamp: %s", timestamp)
            return

        # Store the parsed time and update last added tracker
        measurement["_parsed_time"] = parsed_time
        self._last_added_timestamp = parsed_time

        # Clean old measurements (keep last 60 minutes)
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=60)
        self.history = [
            m for m in self.history
            if m.get("_parsed_time", datetime.min.replace(tzinfo=timezone.utc)) > cutoff
        ]

        # Add new measurement and maintain sorted order
        self.history.append(measurement)
        self.history.sort(key=lambda x: x["_parsed_time"])

        # Trim to max history
        if len(self.history) > self.max_history:
            self.history = self.history[-self.max_history:]

    def calculate_trend(self) -> Dict[str, Any]:
        """Calculate trend based on historical data."""
        _LOGGER.debug("Calculating trend. History count: %d", len(self.history))

        # 1. CHECK FOR STALE DATA (No fresh readings)
        if not self.history:
            _LOGGER.debug("No historical data available.")
            return self._get_stale_data_result(0)

        latest_measurement = self.history[-1]
        latest_time = latest_measurement.get("_parsed_time")
        current_time = datetime.now(latest_time.tzinfo if latest_time.tzinfo else timezone.utc)

        # Define what "too old" means (e.g., more than 10 minutes)
        data_timeout_minutes = 10
        minutes_since_last = (current_time - latest_time).total_seconds() / 60.0

        if minutes_since_last > data_timeout_minutes:
            _LOGGER.warning(
                "Data is stale. Latest measurement is %.1f minutes old. Returning stale state.",
                minutes_since_last
            )
            return self._get_stale_data_result(minutes_since_last)

        # 2. CHECK FOR ENOUGH RECENT DATA
        if len(self.history) < 2:
            _LOGGER.debug("Not enough data for trend calculation (need at least 2 measurements)")
            return self._get_fallback_trend()

        try:
            # Calculate rate of change (mg/dL per minute)
            rate = self._calculate_rate_of_change(self.history)
            _LOGGER.debug("Calculated rate: %f mg/dL per min", rate)

            # Calculate trend based on rate
            trend = self._rate_to_trend(rate)
            _LOGGER.debug("Determined trend: %s", trend)

            # Apply smoothing if we have more history
            if len(self.history) >= 3:
                trend = self._apply_trend_smoothing(trend)
                _LOGGER.debug("After smoothing: %s", trend)

            return {
                "trend": trend,
                "rate": rate,
                "arrow": self._trend_to_arrow(trend),
                "description": self._trend_to_description(trend),
                "calculated": True,
                "history_count": len(self.history),
                "data_is_fresh": True,
                "minutes_since_last": minutes_since_last
            }

        except Exception as e:
            _LOGGER.error("Error calculating trend: %s", e, exc_info=True)
            return self._get_fallback_trend()

    def _calculate_rate_of_change(self, measurements: List[Dict[str, Any]]) -> float:
        """Calculate glucose rate of change in mg/dL per minute."""
        if len(measurements) < 2:
            _LOGGER.debug("DEBUG: Not enough measurements for rate calculation")
            return 0.0
        
        # Sort by time
        measurements.sort(key=lambda x: x["_parsed_time"])
        
        # Calculate multiple rates from different time windows
        rates = []
        weights = []
        latest = measurements[-1]

        # 1-minute rate (most recent)
        if len(measurements) >= 2:
            # Find measurement approximately 1 minute ago
            for i in range(len(measurements)-2, -1, -1):
                time_diff = (latest["_parsed_time"] - measurements[i]["_parsed_time"]).total_seconds() / 60.0
                if 0.5 <= time_diff <= 1.5:  # 1 minute ± 30 seconds
                    rate_1min = (latest["Value"] - measurements[i]["Value"]) / time_diff
                    rates.append(rate_1min)
                    weights.append(3.0)  # Highest weight for 1-min rate
                       
        # 5-minute rate
        if len(measurements) >= 3:
            for i in range(len(measurements)-2, -1, -1):
                time_diff = (latest["_parsed_time"] - measurements[i]["_parsed_time"]).total_seconds() / 60.0
                if 4.0 <= time_diff <= 6.0:  # 5 minutes ± 1 minute
                    rate_5min = (latest["Value"] - measurements[i]["Value"]) / time_diff
                    rates.append(rate_5min)
                    weights.append(2.0)  # Medium weight for 5-min rate
 
        # 15-minute rate
        if len(measurements) >= 4:
            for i in range(len(measurements)-3, -1, -1):
                time_diff = (latest["_parsed_time"] - measurements[i]["_parsed_time"]).total_seconds() / 60.0
                if 14.0 <= time_diff <= 16.0:  # 15 minutes ± 1 minute
                    rate_15min = (latest["Value"] - measurements[i]["Value"]) / time_diff
                    rates.append(rate_15min)
                    weights.append(1.0)  # Lower weight for 15-min rate

        # Calculate weighted average
        if rates:
            weighted_sum = sum(r * w for r, w in zip(rates, weights))
            total_weight = sum(weights)
            final_rate = weighted_sum / total_weight if total_weight > 0 else 0.0
            return final_rate
        
        # Fallback: use simple 2-point calculation
        latest = measurements[-1]
        previous = measurements[-2]
        time_diff = (latest["_parsed_time"] - previous["_parsed_time"]).total_seconds() / 60.0
        if time_diff > 0:
            fallback_rate = (latest["Value"] - previous["Value"]) / time_diff
            return fallback_rate
        
        return 0.0

    def _calculate_delta_for_minutes(self, minutes: int) -> Dict[str, Any]:
        """Calculate value delta for a time window, handling missing data."""
        if len(self.history) < 2:
            return {"delta_value": 0.0, "time_diff": 0.0, "found": False, "note": "not_enough_data"}

        latest = self.history[-1]
        target_time = latest["_parsed_time"] - timedelta(minutes=minutes)

        # Set a tolerance (e.g., ± 20% of the window)
        tolerance_minutes = minutes * 0.2
        earliest_allowed = target_time - timedelta(minutes=tolerance_minutes)
        latest_allowed = target_time + timedelta(minutes=tolerance_minutes)

        for measurement in reversed(self.history[:-1]):
            if earliest_allowed <= measurement["_parsed_time"] <= latest_allowed:
                # Found a measurement within the acceptable time window
                delta_value = latest["Value"] - measurement["Value"]
                actual_time_diff = (latest["_parsed_time"] - measurement["_parsed_time"]).total_seconds() / 60.0
                return {
                    "delta_value": delta_value,
                    "time_diff": actual_time_diff,
                    "found": True,
                    "requested_window": minutes,
                    "actual_window": round(actual_time_diff, 1)
                }

        # If no measurement found in the acceptable window
        return {
            "delta_value": 0.0,
            "time_diff": 0.0,
            "found": False,
            "note": f"no_measurement_{minutes}min_window"
        }

    def calculate_delta_1min(self) -> Dict[str, Any]:
        """Calculate 1-minute delta (value difference over 1 minute)."""
        return self._calculate_delta_for_minutes(1)

    def calculate_delta_5min(self) -> Dict[str, Any]:
        """Calculate 5-minute delta (value difference over 5 minutes)."""
        return self._calculate_delta_for_minutes(5)

    def calculate_delta_15min(self) -> Dict[str, Any]:
        """Calculate 15-minute delta (value difference over 15 minutes)."""
        return self._calculate_delta_for_minutes(15)

    def _get_stale_data_result(self, minutes_since_last: float) -> Dict[str, Any]:
        """Return result indicating data is too old."""
        return {
            "trend": "STALE_DATA",
            "rate": 0.0,
            "arrow": "-",
            "description": f"Data outdated ({minutes_since_last:.0f} min)",
            "calculated": False,
            "history_count": len(self.history),
            "data_is_fresh": False,
            "minutes_since_last": minutes_since_last
        }

    def _rate_to_trend(self, rate: float) -> str:
        """Convert rate of change to trend category."""
        # rate is in mg/dL per minute
        
        # Convert to mmol/L per minute for threshold checking
        rate_mmol = rate * 0.0555
        
        # Use mmol/L thresholds for clarity
        if rate_mmol <= -0.166:           
            result = "FALLING_FAST"
        elif rate_mmol <= -0.055:        
            result = "FALLING"
        elif rate_mmol < 0.055:          
            result = "STABLE"
        elif rate_mmol < 0.166:           
            result = "RISING"
        else:                             
            result = "RISING_FAST"
        
        return result

    def _apply_trend_smoothing(self, current_trend: str) -> str:
        if len(self.history) < 3:
            return current_trend
        recent_trends = []
        for measurement in self.history[-3:]:
            server_trend = measurement.get("TrendArrow", "")
            if server_trend:
                server_trend_cat = self._arrow_to_trend_category(server_trend)
                if server_trend_cat:
                    recent_trends.append(server_trend_cat)
        if not recent_trends:
            return current_trend
        trend_counts = {}
        for trend in recent_trends + [current_trend]:
            trend_counts[trend] = trend_counts.get(trend, 0) + 1
        most_common = max(trend_counts.items(), key=lambda x: x[1])
        if most_common[0] != current_trend and most_common[1] >= 2:
            trend_levels = ["FALLING_FAST", "FALLING", "STABLE", "RISING", "RISING_FAST"]
            current_idx = trend_levels.index(current_trend) if current_trend in trend_levels else -1
            common_idx = trend_levels.index(most_common[0]) if most_common[0] in trend_levels else -1
            if abs(current_idx - common_idx) <= 1:
                return most_common[0]
        return current_trend

    def _arrow_to_trend_category(self, arrow: str) -> Optional[str]:
        arrow_map = {
            "FORTY_FIVE_DOWN": "FALLING",
            "SINGLE_DOWN": "FALLING_FAST",
            "DOUBLE_DOWN": "FALLING_FAST",
            "FORTY_FIVE_UP": "RISING",
            "SINGLE_UP": "RISING_FAST",
            "DOUBLE_UP": "RISING_FAST",
        }
        return arrow_map.get(arrow, None)

    def _trend_to_arrow(self, trend: str) -> str:
        arrow_map = {
            "FALLING_FAST": "↓",
            "FALLING": "↘",
            "STABLE": "→",
            "RISING": "↗",
            "RISING_FAST": "↑",
        }
        return arrow_map.get(trend, "→")

    def _trend_to_description(self, trend: str) -> str:
        desc_map = {
            "FALLING_FAST": "Falling fast",
            "FALLING": "Falling",
            "STABLE": "Stable",
            "RISING": "Rising",
            "RISING_FAST": "Rising fast",
        }
        return desc_map.get(trend, "Stable")

    def _get_fallback_trend(self) -> Dict[str, Any]:
        if not self.history:
            return {
                "trend": "STABLE",
                "rate": 0.0,
                "arrow": "→",
                "description": "Stable",
                "calculated": False,
                "history_count": 0,
                "data_is_fresh": False,
                "minutes_since_last": 999
            }
        latest = self.history[-1]
        server_trend = latest.get("TrendArrow", "")
        trend_cat = self._arrow_to_trend_category(server_trend) or "STABLE"
        return {
            "trend": trend_cat,
            "rate": 0.0,
            "arrow": self._trend_to_arrow(trend_cat),
            "description": self._trend_to_description(trend_cat),
            "calculated": False,
            "history_count": len(self.history),
            "data_is_fresh": True,
            "minutes_since_last": 0
        }

    def clear_history(self) -> None:
        self.history.clear()
        _LOGGER.debug("Cleared trend calculation history")

    def _calculate_rate_between(self, earlier: Dict[str, Any], later: Dict[str, Any]) -> float:
        time_diff_min = (later["_parsed_time"] - earlier["_parsed_time"]).total_seconds() / 60.0
        if time_diff_min <= 0:
            return 0.0
        value_diff = later["Value"] - earlier["Value"]
        return value_diff / time_diff_min