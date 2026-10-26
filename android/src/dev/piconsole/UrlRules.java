// SPDX-License-Identifier: Apache-2.0
package dev.piconsole;

import java.net.URI;
import java.net.URISyntaxException;
import java.util.Locale;

final class UrlRules {
    static String validate(String raw) {
        if (raw == null || raw.isEmpty()) throw new IllegalArgumentException("请输入网址");
        for (int i = 0; i < raw.length(); i++) {
            char c = raw.charAt(i);
            if (Character.isISOControl(c) || Character.isWhitespace(c)) throw new IllegalArgumentException("网址不能包含空格或控制字符");
        }
        try {
            URI uri = new URI(raw);
            String scheme = uri.getScheme();
            if (scheme == null || !(scheme.toLowerCase(Locale.ROOT).equals("http") || scheme.toLowerCase(Locale.ROOT).equals("https"))
                    || uri.getHost() == null || uri.getHost().isEmpty() || uri.getRawUserInfo() != null
                    || uri.getPort() > 65535 || uri.getPort() < -1)
                throw new IllegalArgumentException("仅支持带有效主机名的 HTTP 或 HTTPS 网址");
            return raw;
        } catch (URISyntaxException ex) {
            throw new IllegalArgumentException("网址格式无效", ex);
        }
    }
}
