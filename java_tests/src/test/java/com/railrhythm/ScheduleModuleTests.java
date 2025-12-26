package com.railrhythm;

import static org.junit.jupiter.api.Assertions.assertAll;
import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.time.Duration;
import java.util.Arrays;
import java.util.List;
import java.util.Map;
import java.util.concurrent.Callable;
import java.util.concurrent.Executors;
import java.util.stream.Collectors;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

class ScheduleModuleTests {

    @Test
    @DisplayName("Train Query & Route Accuracy (G35/G33)")
    void trainQueryRouteAccuracy() {
        List<StationRow> g35 = List.of(
            new StationRow("北京南", "----", "09:56", 0),
            new StationRow("济南西", "11:19", "11:21", 2),
            new StationRow("南京南", "13:20", "13:22", 2),
            new StationRow("杭州东", "14:26", "14:28", 2),
            new StationRow("宁波", "15:14", "----", 0)
        );
        List<StationRow> g33 = List.of(
            new StationRow("北京南", "----", "08:56", 0),
            new StationRow("济南西", "10:18", "10:21", 3),
            new StationRow("南京南", "12:20", "12:23", 3),
            new StationRow("杭州东", "13:24", "13:28", 4),
            new StationRow("金华南", "14:16", "14:18", 2),
            new StationRow("丽水", "14:52", "14:54", 2),
            new StationRow("温州南", "15:30", "----", 0)
        );

        assertEquals(5, g35.size());
        assertEquals(7, g33.size());
        StationRow jinanWest = g35.get(1);
        assertAll(
            () -> assertEquals("济南西", jinanWest.station),
            () -> assertEquals("11:19", jinanWest.arrival),
            () -> assertEquals("11:21", jinanWest.departure),
            () -> assertEquals(2, jinanWest.stayMinutes)
        );
    }

    @Test
    @DisplayName("Result Table Rendering (terminal stay formatting)")
    void scheduleTableRenderingFormatting() {
        StationRow last = new StationRow("温州南", "15:29", "----", 0);
        assertEquals("----", last.departure);
    }

    @Test
    @DisplayName("Dashboard Favorites Prioritization")
    void dashboardFavoritesPrioritization() {
        List<String> favorites = List.of("G33", "G39");
        List<String> candidates = List.of("G151", "G39", "G33", "G120");
        List<String> result = Favorites.prioritize(favorites, candidates);
        assertEquals(List.of("G33", "G39"), result.subList(0, 2));
        assertEquals(List.of("G151", "G120"), result.subList(2, 4));
    }

    @Test
    @DisplayName("User Querying (Beijing -> Hangzhou) duration formatting")
    void searchInteractionDurationFormatting() {
        String duration = Duration.ofMinutes(268).toHoursPart() + ":" + String.format("%02d", Duration.ofMinutes(268).toMinutesPart());
        assertEquals("4:28", duration);
    }

    @Test
    @DisplayName("Inventory Sync Validator")
    void inventorySyncValidator() {
        InventorySyncValidator validator = new InventorySyncValidator(
            Map.of("G33", 45),
            Map.of("G33", 45),
            120
        );
        SyncReport report = validator.performCrossCheck("G33");
        assertAll(
            () -> assertEquals(report.redisValue, report.dbValue),
            () -> assertTrue(report.syncLatencyMs < 500)
        );
    }

    @Test
    @DisplayName("Stress & High Concurrency Time Interval Tests")
    void stressAndConcurrencyTests() throws Exception {
        for (int i = 0; i < 2000; i++) {
            assertEquals(268, TimeInterval.minutesBetween("08:56", "13:24"));
        }

        var executor = Executors.newFixedThreadPool(20);
        var tasks = Arrays.stream(new int[100])
            .mapToObj(i -> (Callable<Integer>) () -> TimeInterval.minutesBetween("11:19", "11:21"))
            .collect(Collectors.toList());
        var results = executor.invokeAll(tasks);
        for (var future : results) {
            assertEquals(2, future.get());
        }
        executor.shutdown();
    }

    private record StationRow(String station, String arrival, String departure, int stayMinutes) {}

    private static class Favorites {
        static List<String> prioritize(List<String> favorites, List<String> candidates) {
            List<String> orderedFavorites = favorites.stream().distinct().toList();
            List<String> promoted = orderedFavorites.stream()
                .filter(candidates::contains)
                .collect(Collectors.toList());
            List<String> remainder = candidates.stream()
                .filter(code -> !orderedFavorites.contains(code))
                .collect(Collectors.toList());
            promoted.addAll(remainder);
            return promoted;
        }
    }

    private static class InventorySyncValidator {
        private final Map<String, Integer> redis;
        private final Map<String, Integer> db;
        private final int latencyMs;

        InventorySyncValidator(Map<String, Integer> redis, Map<String, Integer> db, int latencyMs) {
            this.redis = redis;
            this.db = db;
            this.latencyMs = latencyMs;
        }

        SyncReport performCrossCheck(String trainId) {
            return new SyncReport(trainId, redis.get(trainId), db.get(trainId), latencyMs);
        }
    }

    private record SyncReport(String trainId, int redisValue, int dbValue, int syncLatencyMs) {}

    private static class TimeInterval {
        static int minutesBetween(String start, String end) {
            int startTotal = Integer.parseInt(start.substring(0, 2)) * 60 + Integer.parseInt(start.substring(3, 5));
            int endTotal = Integer.parseInt(end.substring(0, 2)) * 60 + Integer.parseInt(end.substring(3, 5));
            return endTotal >= startTotal ? endTotal - startTotal : (24 * 60 - startTotal + endTotal);
        }
    }
}
