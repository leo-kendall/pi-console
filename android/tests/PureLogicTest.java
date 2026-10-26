// SPDX-License-Identifier: Apache-2.0
package dev.piconsole;

import java.io.ByteArrayInputStream;
import java.io.IOException;
import java.nio.charset.StandardCharsets;

public final class PureLogicTest {
    private static int checks;

    private static void equal(Object want, Object got) {
        checks++;
        if (!want.equals(got)) throw new AssertionError("want " + want + ", got " + got);
    }

    private static void rejected(Throwing action) {
        checks++;
        try { action.run(); } catch (IOException | IllegalArgumentException expected) { return; }
        throw new AssertionError("accepted invalid input");
    }

    private interface Throwing { void run() throws IOException; }

    private static String parse(String response) throws IOException {
        return HttpResponseParser.readJson(new ByteArrayInputStream(response.getBytes(StandardCharsets.UTF_8)));
    }

    public static void main(String[] args) throws Exception {
        equal("{\"ok\":true}", parse("HTTP/1.1 200 OK\r\nContent-Length: 11\r\n\r\n{\"ok\":true}"));
        equal("{\"a\":1}", parse("HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n3\r\n{\"a\r\n4\r\n\":1}\r\n0\r\n\r\n"));
        rejected(() -> parse("HTTP/1.1 403 Forbidden\r\nContent-Length: 2\r\n\r\n{}"));
        rejected(() -> parse("HTTP/1.1 200 OK\r\nContent-Length: 10\r\n\r\n{}"));
        rejected(() -> parse("HTTP/1.1 200 OK\r\nContent-Length: 1048577\r\n\r\n"));
        rejected(() -> parse("HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n100001\r\n"));
        rejected(() -> parse("HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n3\r\n{}\r\n0\r\n\r\n"));
        equal("https://example.com/path", UrlRules.validate("https://example.com/path"));
        rejected(() -> UrlRules.validate("javascript:alert(1)"));
        rejected(() -> UrlRules.validate("file:///etc/passwd"));
        rejected(() -> UrlRules.validate("content://contacts/1"));
        rejected(() -> UrlRules.validate("https://example.com/\nattack"));
        rejected(() -> UrlRules.validate("https://user:secret@example.com"));
        PollGate gate = new PollGate();
        gate.enter();
        long first = gate.begin();
        equal(true, first >= 0);
        equal(-1L, gate.begin());
        gate.leave();
        gate.enter();
        equal(false, gate.finish(first));
        long second = gate.begin();
        equal(true, second > first);
        equal(true, gate.finish(second));
        gate.leave();
        equal(-1L, gate.begin());
        System.out.println("PASS " + checks + " pure-Java assertions");
    }
}
