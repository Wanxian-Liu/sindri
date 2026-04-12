"""
Test circuit_breaker.py __main__ block and edge cases
"""
import sys
import os
import subprocess
import pytest

SCRIPTS_DIR = os.path.expanduser("~/.openclaw/skills/sindris/scripts")


class TestCircuitBreakerMain:
    """Test circuit_breaker.py __main__ block"""

    def test_main_runs_without_error(self):
        """Test that __main__ block executes without error"""
        result = subprocess.run(
            [sys.executable, "-c", f"""
import sys
sys.path.insert(0, '{SCRIPTS_DIR}')
import circuit_breaker
print("CircuitBreaker loaded successfully")
"""],
            capture_output=True,
            text=True,
            timeout=10
        )
        assert "CircuitBreaker loaded successfully" in result.stdout
        assert result.returncode == 0

    def test_circuit_breaker_enum_values(self):
        """Test CircuitState enum has expected values"""
        sys.path.insert(0, SCRIPTS_DIR)
        # Clear cache to reimport
        if 'circuit_breaker' in sys.modules:
            del sys.modules['circuit_breaker']
        if '_circuit_breakers' in sys.modules:
            del sys.modules['_circuit_breakers']
        import circuit_breaker
        assert circuit_breaker.CircuitState.CLOSED.value == "closed"
        assert circuit_breaker.CircuitState.OPEN.value == "open"
        assert circuit_breaker.CircuitState.HALF_OPEN.value == "half_open"

    def test_role_timeouts_keys(self):
        """Test ROLE_TIMEOUTS has expected keys"""
        sys.path.insert(0, SCRIPTS_DIR)
        if 'circuit_breaker' in sys.modules:
            del sys.modules['circuit_breaker']
        import circuit_breaker
        expected_keys = {"researcher", "developer", "verifier", "recorder"}
        assert set(circuit_breaker.ROLE_TIMEOUTS.keys()) == expected_keys

    def test_get_circuit_status(self):
        """Test get_circuit_status function"""
        sys.path.insert(0, SCRIPTS_DIR)
        if 'circuit_breaker' in sys.modules:
            del sys.modules['circuit_breaker']
        import circuit_breaker
        circuit_breaker._circuit_breakers.clear()
        status = circuit_breaker.get_circuit_status("developer")
        assert status["role_type"] == "developer"
        assert status["state"] == "closed"
        assert status["failures"] == 0

    def test_reset_circuit(self):
        """Test reset_circuit function"""
        sys.path.insert(0, SCRIPTS_DIR)
        if 'circuit_breaker' in sys.modules:
            del sys.modules['circuit_breaker']
        import circuit_breaker
        circuit_breaker._circuit_breakers.clear()
        circuit_breaker.get_circuit_breaker("developer")
        result = circuit_breaker.reset_circuit("developer")
        assert result["role_type"] == "developer"
        assert result["status"] == "reset"

    def test_get_all_circuits_status(self):
        """Test get_all_circuits_status function"""
        sys.path.insert(0, SCRIPTS_DIR)
        if 'circuit_breaker' in sys.modules:
            del sys.modules['circuit_breaker']
        import circuit_breaker
        circuit_breaker._circuit_breakers.clear()
        circuit_breaker.get_circuit_breaker("researcher")
        circuit_breaker.get_circuit_breaker("developer")
        all_status = circuit_breaker.get_all_circuits_status()
        assert "researcher" in all_status
        assert "developer" in all_status

    def test_circuit_open_error_is_exception(self):
        """Test CircuitOpenError is a proper exception"""
        sys.path.insert(0, SCRIPTS_DIR)
        if 'circuit_breaker' in sys.modules:
            del sys.modules['circuit_breaker']
        import circuit_breaker
        err = circuit_breaker.CircuitOpenError("test error")
        assert isinstance(err, Exception)
        assert str(err) == "test error"

    def test_with_circuit_breaker_decorator(self):
        """Test with_circuit_breaker decorator"""
        sys.path.insert(0, SCRIPTS_DIR)
        if 'circuit_breaker' in sys.modules:
            del sys.modules['circuit_breaker']
        import circuit_breaker

        @circuit_breaker.with_circuit_breaker(role_type="developer")
        def dummy_func():
            return "success"

        result = dummy_func()
        assert result == "success"

    def test_execute_with_circuit_breaker_success(self):
        """Test execute_with_circuit_breaker with successful execution"""
        sys.path.insert(0, SCRIPTS_DIR)
        if 'circuit_breaker' in sys.modules:
            del sys.modules['circuit_breaker']
        import circuit_breaker
        circuit_breaker._circuit_breakers.clear()

        def dummy_func():
            return "done"

        result = circuit_breaker.execute_with_circuit_breaker(
            session_key="test-session",
            role_type="developer",
            func=dummy_func
        )
        assert result == "done"

    def test_execute_with_circuit_breaker_open_raises(self):
        """Test execute_with_circuit_breaker raises when circuit is open"""
        sys.path.insert(0, SCRIPTS_DIR)
        if 'circuit_breaker' in sys.modules:
            del sys.modules['circuit_breaker']
        import circuit_breaker
        circuit_breaker._circuit_breakers.clear()

        cb = circuit_breaker.get_circuit_breaker("developer")
        for _ in range(10):
            cb.record_failure()

        def dummy_func():
            return "done"

        with pytest.raises(circuit_breaker.CircuitOpenError):
            circuit_breaker.execute_with_circuit_breaker(
                session_key="test-session",
                role_type="developer",
                func=dummy_func
            )
