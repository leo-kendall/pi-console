// SPDX-License-Identifier: Apache-2.0
package dev.piconsole;
import java.net.*;
import javax.net.ssl.*;
public final class ProbeRulesTest {
 public static void main(String[] args)throws Exception {
  check(ProbeRules.http(200).equals("inspect"),"200 needs identity check");
  check(ProbeRules.http(302).equals("redirect"),"do not follow redirect");
  check(ProbeRules.http(404).equals("missing"),"old backend/path hint");
  check(ProbeRules.http(403).equals("denied"),"proxy firewall");
  check(ProbeRules.http(502).equals("upstream"),"reverse proxy backend failure");
  check(ProbeRules.failure(new UnknownHostException("secret.example")).equals("dns"),"DNS classification");
  check(ProbeRules.failure(new SocketTimeoutException()).equals("timeout"),"timeout classification");
  check(ProbeRules.failure(new ConnectException()).equals("connect"),"connection classification");
  check(ProbeRules.failure(new SSLHandshakeException("private cert")).equals("tls"),"TLS classification");
  check(ProbeRules.failure(new RuntimeException(new SSLPeerUnverifiedException("private subject"))).equals("tls"),"wrapped TLS error");
  check(ProbeRules.identity("application/json; charset=utf-8","{\"app\":\"pi-console\",\"protocol\":1}").equals("ok"),"compatible backend");
  check(ProbeRules.identity("application/json","{\"app\":\"pi-console\",\"protocol\":2}").equals("version"),"future backend");
  check(ProbeRules.identity("text/html","<html>secret-body</html>").equals("response"),"wrong URL HTML");
  check(ProbeRules.identity("application/json","{\"app\":\"other\",\"protocol\":1}").equals("response"),"other product");
  check(ProbeRules.identity("application/json","{\"app\":\"pi-console\",\"protocol\":\"1\"}").equals("response"),"protocol must be integer");
  check(ProbeRules.identity("application/json","{\"app\":\"pi-console\",\"protocol\":1}garbage").equals("response"),"trailing data");
  check(ProbeRules.identity("application/json","{broken").equals("response"),"invalid JSON");
  check(ProbeRules.identity("application/json",new String(new char[8193])).equals("response"),"bounded response");
  for(String code:new String[]{"dns","timeout","connect","tls","redirect","missing","denied","upstream","response","version","network"}) {
   check(!ProbeRules.title(code).isEmpty()&&!ProbeRules.detail(code).isEmpty(),"actionable safe message: "+code);
  }
  check(ProbeRules.pairingError(401).contains("过期"),"expired pairing code guidance");
  check(ProbeRules.pairingError(429).contains("分钟"),"pair rate-limit guidance");
  System.out.println("Connection diagnosis classification and backend identity tests passed");
 }
 static void check(boolean value,String message){if(!value)throw new AssertionError(message);}
}
