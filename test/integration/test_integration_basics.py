#!/usr/bin/env python3

import logging
import os
import sys
import pytest

from common import IpVersion
from integration_test_fixtures import (http_test_server_fixture, https_test_server_fixture)

# TODO(oschaaf): rewrite the tests so we can just hand a map of expected key values to it.
# TODO(oschaaf): we mostly verify stats observed from the client-side. Add expectations
# for the server side as well.


def assertEqual(a, b):
  assert a == b


def assertGreater(a, b):
  assert a > b


def assertGreaterEqual(a, b):
  assert a >= b


def assertLessEqual(a, b):
  assert a <= b


def assertNotIn(a, b):
  assert a not in b


def assertIn(a, b):
  assert a in b


def test_http_h1(http_test_server_fixture):
  """
  Runs the CLI configured to use plain HTTP/1 against our test server, and sanity
  checks statistics from both client and server.
  """
  parsed_json, _ = http_test_server_fixture.runNighthawkClient(
      [http_test_server_fixture.getTestServerRootUri()])
  counters = http_test_server_fixture.getNighthawkCounterMapFromJson(parsed_json)
  assertEqual(counters["benchmark.http_2xx"], 25)
  assertEqual(counters["upstream_cx_destroy"], 1)
  assertEqual(counters["upstream_cx_destroy_local"], 1)
  assertEqual(counters["upstream_cx_http1_total"], 1)
  assertEqual(counters["upstream_cx_rx_bytes_total"], 3400)
  assertEqual(counters["upstream_cx_total"], 1)
  assertEqual(counters["upstream_cx_tx_bytes_total"],
              1400 if http_test_server_fixture.ip_version == IpVersion.IPV6 else 1500)
  assertEqual(counters["upstream_rq_pending_total"], 1)
  assertEqual(counters["upstream_rq_total"], 25)
  assertEqual(len(counters), 9)


def mini_stress_test_h1(fixture, args):
  # run a test with more rps then we can handle, and a very small client-side queue.
  # we should observe both lots of successfull requests as well as time spend in blocking mode.,
  parsed_json, _ = fixture.runNighthawkClient(args)
  counters = fixture.getNighthawkCounterMapFromJson(parsed_json)
  # We set a reasonably low expecation of 100 requests. We set it low, because we want this
  # test to succeed on a reasonable share of setups (hopefully practically all).
  MIN_EXPECTED_REQUESTS = 100
  assertGreater(counters["benchmark.http_2xx"], MIN_EXPECTED_REQUESTS)
  assertEqual(counters["upstream_cx_http1_total"], 1)
  global_histograms = fixture.getNighthawkGlobalHistogramsbyIdFromJson(parsed_json)
  assertGreater(int(global_histograms["sequencer.blocking"]["count"]), MIN_EXPECTED_REQUESTS)
  assertGreater(
      int(global_histograms["benchmark_http_client.request_to_response"]["count"]),
      MIN_EXPECTED_REQUESTS)
  return counters


def test_http_h1_mini_stress_test_with_client_side_queueing(http_test_server_fixture):
  """
  Run a max rps test with the h1 pool against our test server, using a small client-side
  queue. We expect to observe:
  - upstream_rq_pending_total increasing
  - upstream_cx_overflow overflows
  - blocking to be reported by the sequencer
  """
  counters = mini_stress_test_h1(http_test_server_fixture, [
      http_test_server_fixture.getTestServerRootUri(), "--rps", "999999", "--max-pending-requests",
      "10", "--duration 2"
  ])
  assertGreater(counters["upstream_rq_pending_total"], 100)
  assertGreater(counters["upstream_cx_overflow"], 0)


def test_http_h1_mini_stress_test_without_client_side_queueing(http_test_server_fixture):
  """
  Run a max rps test with the h1 pool against our test server, with no client-side
  queueing. We expect to observe:
  - upstream_rq_pending_total to be equal to 1
  - blocking to be reported by the sequencer
  - no upstream_cx_overflows
  """
  counters = mini_stress_test_h1(
      http_test_server_fixture,
      [http_test_server_fixture.getTestServerRootUri(), "--rps", "999999", "--duration 2"])
  assertEqual(counters["upstream_rq_pending_total"], 1)
  assertNotIn("upstream_cx_overflow", counters)


def test_http_h2(http_test_server_fixture):
  """
  Runs the CLI configured to use h2c against our test server, and sanity
  checks statistics from both client and server.
  """
  parsed_json, _ = http_test_server_fixture.runNighthawkClient(
      ["--h2", http_test_server_fixture.getTestServerRootUri()])
  counters = http_test_server_fixture.getNighthawkCounterMapFromJson(parsed_json)
  assertEqual(counters["benchmark.http_2xx"], 25)
  assertEqual(counters["upstream_cx_destroy"], 1)
  assertEqual(counters["upstream_cx_destroy_local"], 1)
  assertEqual(counters["upstream_cx_http2_total"], 1)
  assertGreaterEqual(counters["upstream_cx_rx_bytes_total"], 1145)
  assertEqual(counters["upstream_cx_total"], 1)
  assertGreaterEqual(counters["upstream_cx_tx_bytes_total"], 403)
  assertEqual(counters["upstream_rq_pending_total"], 1)
  assertEqual(counters["upstream_rq_total"], 25)
  assertEqual(len(counters), 9)


def test_http_concurrency(http_test_server_fixture):
  """
  Concurrency should act like a multiplier.
  """

  parsed_json, _ = http_test_server_fixture.runNighthawkClient(
      ["--concurrency 4 --rps 5 --connections 1",
       http_test_server_fixture.getTestServerRootUri()])
  counters = http_test_server_fixture.getNighthawkCounterMapFromJson(parsed_json)

  assertGreater(counters["benchmark.http_2xx"], 25)
  assertLessEqual(counters["benchmark.http_2xx"], 100)
  assertEqual(counters["upstream_cx_http1_total"], 4)


def test_https_h1(https_test_server_fixture):
  """
  Runs the CLI configured to use HTTP/1 over https against our test server, and sanity
  checks statistics from both client and server.
  """
  parsed_json, _ = https_test_server_fixture.runNighthawkClient(
      [https_test_server_fixture.getTestServerRootUri()])
  counters = https_test_server_fixture.getNighthawkCounterMapFromJson(parsed_json)
  assertEqual(counters["benchmark.http_2xx"], 25)
  assertEqual(counters["upstream_cx_destroy"], 1)
  assertEqual(counters["upstream_cx_destroy_local"], 1)
  assertEqual(counters["upstream_cx_http1_total"], 1)
  assertEqual(counters["upstream_cx_rx_bytes_total"], 3400)
  assertEqual(counters["upstream_cx_total"], 1)
  assertEqual(counters["upstream_cx_tx_bytes_total"],
              1400 if https_test_server_fixture.ip_version == IpVersion.IPV6 else 1500)
  assertEqual(counters["upstream_rq_pending_total"], 1)
  assertEqual(counters["upstream_rq_total"], 25)
  assertEqual(counters["ssl.ciphers.ECDHE-RSA-AES128-GCM-SHA256"], 1)
  assertEqual(counters["ssl.curves.X25519"], 1)
  assertEqual(counters["ssl.handshake"], 1)
  assertEqual(counters["ssl.sigalgs.rsa_pss_rsae_sha256"], 1)
  assertEqual(counters["ssl.versions.TLSv1.2"], 1)
  assertEqual(len(counters), 14)

  server_stats = https_test_server_fixture.getTestServerStatisticsJson()
  assertEqual(
      https_test_server_fixture.getServerStatFromJson(server_stats,
                                                      "http.ingress_http.downstream_rq_2xx"), 25)


def test_https_h2(https_test_server_fixture):
  """
  Runs the CLI configured to use HTTP/2 (using https) against our test server, and sanity
  checks statistics from both client and server.
  """

  parsed_json, _ = https_test_server_fixture.runNighthawkClient(
      ["--h2", https_test_server_fixture.getTestServerRootUri()])
  counters = https_test_server_fixture.getNighthawkCounterMapFromJson(parsed_json)
  assertEqual(counters["benchmark.http_2xx"], 25)
  assertEqual(counters["upstream_cx_destroy"], 1)
  assertEqual(counters["upstream_cx_destroy_local"], 1)
  assertEqual(counters["upstream_cx_http2_total"], 1)
  assertGreaterEqual(counters["upstream_cx_rx_bytes_total"], 1145)
  assertEqual(counters["upstream_cx_total"], 1)
  assertGreaterEqual(counters["upstream_cx_tx_bytes_total"], 403)
  assertEqual(counters["upstream_rq_pending_total"], 1)
  assertEqual(counters["upstream_rq_total"], 25)
  assertEqual(counters["ssl.ciphers.ECDHE-RSA-AES128-GCM-SHA256"], 1)
  assertEqual(counters["ssl.curves.X25519"], 1)
  assertEqual(counters["ssl.handshake"], 1)
  assertEqual(counters["ssl.sigalgs.rsa_pss_rsae_sha256"], 1)
  assertEqual(counters["ssl.versions.TLSv1.2"], 1)
  assertEqual(len(counters), 14)


def test_https_h1_tls_context_configuration(https_test_server_fixture):
  """
  Verifies specifying tls cipher suites works with the h1 pool
  """

  parsed_json, _ = https_test_server_fixture.runNighthawkClient([
      "--duration 1",
      "--tls-context {common_tls_context:{tls_params:{cipher_suites:[\"-ALL:ECDHE-RSA-AES128-SHA\"]}}}",
      https_test_server_fixture.getTestServerRootUri()
  ])
  counters = https_test_server_fixture.getNighthawkCounterMapFromJson(parsed_json)
  assertEqual(counters["ssl.ciphers.ECDHE-RSA-AES128-SHA"], 1)

  parsed_json, _ = https_test_server_fixture.runNighthawkClient([
      "--h2", "--duration 1",
      "--tls-context {common_tls_context:{tls_params:{cipher_suites:[\"-ALL:ECDHE-RSA-AES256-GCM-SHA384\"]}}}",
      https_test_server_fixture.getTestServerRootUri()
  ])
  counters = https_test_server_fixture.getNighthawkCounterMapFromJson(parsed_json)
  assertEqual(counters["ssl.ciphers.ECDHE-RSA-AES256-GCM-SHA384"], 1)


def test_https_h2_tls_context_configuration(https_test_server_fixture):
  """
  Verifies specifying tls cipher suites works with the h2 pool
  """
  parsed_json, _ = https_test_server_fixture.runNighthawkClient([
      "--duration 1",
      "--tls-context {common_tls_context:{tls_params:{cipher_suites:[\"-ALL:ECDHE-RSA-AES128-SHA\"]}}}",
      https_test_server_fixture.getTestServerRootUri()
  ])
  counters = https_test_server_fixture.getNighthawkCounterMapFromJson(parsed_json)
  assertEqual(counters["ssl.ciphers.ECDHE-RSA-AES128-SHA"], 1)

  parsed_json, _ = https_test_server_fixture.runNighthawkClient([
      "--h2", "--duration 1",
      "--tls-context {common_tls_context:{tls_params:{cipher_suites:[\"-ALL:ECDHE-RSA-AES256-GCM-SHA384\"]}}}",
      https_test_server_fixture.getTestServerRootUri()
  ])
  counters = https_test_server_fixture.getNighthawkCounterMapFromJson(parsed_json)
  assertEqual(counters["ssl.ciphers.ECDHE-RSA-AES256-GCM-SHA384"], 1)


def test_https_prefetching(https_test_server_fixture):
  """
  Test we prefetch connections. We test for 1 second at 1 rps, which should
  result in 1 connection max without prefetching. However, we specify 50 connections
  and the prefetching flag, so we ought to see 50 http1 connections created.
  """
  parsed_json, _ = https_test_server_fixture.runNighthawkClient([
      "--duration 1", "--rps 1", "--prefetch-connections", "--connections 50",
      https_test_server_fixture.getTestServerRootUri()
  ])
  counters = https_test_server_fixture.getNighthawkCounterMapFromJson(parsed_json)
  assertEqual(counters["upstream_cx_http1_total"], 50)


def test_https_log_verbosity(https_test_server_fixture):
  """
  Test that that the specified log verbosity level is respected.
  This tests for a sentinel we know is only right when the level
  is set to 'trace'.
  """
  # TODO(oschaaf): this is kind of fragile. Can we improve?
  trace_level_sentinel = "nighthawk_service_zone"
  _, logs = https_test_server_fixture.runNighthawkClient(
      ["--duration 1", "--rps 1", "-v debug",
       https_test_server_fixture.getTestServerRootUri()])
  assertNotIn(trace_level_sentinel, logs)

  _, logs = https_test_server_fixture.runNighthawkClient(
      ["--duration 1", "--rps 1", "-v trace",
       https_test_server_fixture.getTestServerRootUri()])
  assertIn(trace_level_sentinel, logs)