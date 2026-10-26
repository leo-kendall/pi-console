// SPDX-License-Identifier: Apache-2.0
package dev.piconsole;

import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.nio.ByteBuffer;
import java.nio.charset.CharacterCodingException;
import java.nio.charset.StandardCharsets;
import java.nio.charset.CodingErrorAction;
import java.util.Locale;

final class HttpResponseParser {
    private static final int MAX_BODY = 1024 * 1024;
    private static final int MAX_HEADERS = 16 * 1024;
    private static final int MAX_LINE = 8192;

    static String readJson(InputStream input) throws IOException {
        int[] budget = {MAX_HEADERS};
        String status = line(input, budget);
        if (!status.matches("HTTP/1\\.[01] [0-9]{3}(?: .*)?")) throw new IOException("Invalid HTTP status");
        boolean success=status.matches("HTTP/1\\.[01] 200(?: .*)?");
        Long length = null;
        String encoding = null;
        while (true) {
            String header = line(input, budget);
            if (header.isEmpty()) break;
            int colon = header.indexOf(':');
            if (colon < 1) throw new IOException("Malformed HTTP header");
            String name = header.substring(0, colon).trim().toLowerCase(Locale.ROOT);
            String value = header.substring(colon + 1).trim();
            if (name.equals("content-length")) {
                if (length != null || !value.matches("[0-9]+")) throw new IOException("Invalid Content-Length");
                try { length = Long.parseLong(value); } catch (NumberFormatException ex) { throw new IOException("Invalid Content-Length", ex); }
                if (length > MAX_BODY) throw new IOException("Response too large");
            } else if (name.equals("transfer-encoding")) {
                if (encoding != null) throw new IOException("Duplicate Transfer-Encoding");
                encoding = value.toLowerCase(Locale.ROOT);
            }
        }
        if (length != null && encoding != null) throw new IOException("Ambiguous body framing");
        byte[] body;
        if (encoding != null) {
            if (!encoding.equals("chunked")) throw new IOException("Unsupported Transfer-Encoding");
            body = chunks(input, budget);
        } else if (length != null) {
            body = fixed(input, length.intValue());
        } else {
            body = untilEnd(input);
        }
        try {
            String text=StandardCharsets.UTF_8.newDecoder()
                    .onMalformedInput(CodingErrorAction.REPORT)
                    .onUnmappableCharacter(CodingErrorAction.REPORT)
                    .decode(ByteBuffer.wrap(body)).toString();
            if(!success) {
                if(status.contains(" 401 "))throw new IOException("请先在设置中配对设备");
                if(status.contains(" 429 "))throw new IOException("操作过快，请稍后重试");
                if(status.contains(" 409 "))throw new IOException("对象或状态已变化，请刷新后重新确认");
                throw new IOException("请求失败（"+status.substring(9,12)+"），请刷新状态或检查服务器");
            }
            return text;
        } catch (CharacterCodingException ex) {
            throw new IOException("Invalid UTF-8", ex);
        }
    }

    private static String line(InputStream input, int[] budget) throws IOException {
        ByteArrayOutputStream bytes = new ByteArrayOutputStream();
        while (true) {
            int b = input.read();
            if (b < 0 || --budget[0] < 0) throw new IOException("Truncated or oversized HTTP header");
            if (b == '\r') {
                int next = input.read();
                if (next != '\n' || --budget[0] < 0) throw new IOException("Expected CRLF");
                return bytes.toString("ISO-8859-1");
            }
            if (b == '\n' || bytes.size() >= MAX_LINE) throw new IOException("Invalid HTTP line");
            bytes.write(b);
        }
    }

    private static byte[] fixed(InputStream input, int length) throws IOException {
        byte[] bytes = new byte[length];
        int offset = 0;
        while (offset < length) {
            int count = input.read(bytes, offset, length - offset);
            if (count < 0) throw new IOException("Truncated HTTP body");
            offset += count;
        }
        return bytes;
    }

    private static byte[] chunks(InputStream input, int[] budget) throws IOException {
        ByteArrayOutputStream body = new ByteArrayOutputStream();
        while (true) {
            String sizeLine = line(input, budget);
            int semicolon = sizeLine.indexOf(';');
            String hex = (semicolon < 0 ? sizeLine : sizeLine.substring(0, semicolon)).trim();
            if (!hex.matches("[0-9a-fA-F]+")) throw new IOException("Invalid chunk size");
            long size;
            try { size = Long.parseLong(hex, 16); } catch (NumberFormatException ex) { throw new IOException("Invalid chunk size", ex); }
            if (size > MAX_BODY - body.size()) throw new IOException("Chunked response too large");
            if (size == 0) {
                while (!line(input, budget).isEmpty()) { /* bounded trailers */ }
                return body.toByteArray();
            }
            body.write(fixed(input, (int) size));
            if (input.read() != '\r' || input.read() != '\n') throw new IOException("Invalid chunk terminator");
        }
    }

    private static byte[] untilEnd(InputStream input) throws IOException {
        ByteArrayOutputStream body = new ByteArrayOutputStream();
        byte[] buffer = new byte[4096];
        int count;
        while ((count = input.read(buffer)) != -1) {
            if (count > MAX_BODY - body.size()) throw new IOException("Response too large");
            body.write(buffer, 0, count);
        }
        return body.toByteArray();
    }
}
