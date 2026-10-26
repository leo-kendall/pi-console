// SPDX-License-Identifier: Apache-2.0
package dev.piconsole;
public final class ServerEndpointTest {
 public static void main(String[] args)throws Exception {
  ServerEndpoint endpoint=ServerEndpoint.parse("https://console.example.test:8443/pi-console/");
  check(endpoint.port==8443,"port");check(endpoint.host.equals("console.example.test"),"host");
  check(endpoint.path("/api/status").equals("/pi-console/api/status"),"path prefix");
  check(endpoint.canonical.equals("https://console.example.test:8443/pi-console"),"canonical");
  check(ServerEndpoint.parse("https://console.example.test").path("/api/pair").equals("/api/pair"),"root endpoint");
  for(String url:new String[]{"http://console.example.test","https://u:p@host/","https://host/?token=x","https://host/#frag","https://host:99999","https://host/a/../b","https://host/%2e%2e/x","https://host/a\\b","https://host/\r\nInjected: x"}) {
   boolean rejected=false;try{ServerEndpoint.parse(url);}catch(IllegalArgumentException e){rejected=true;}check(rejected,"reject "+url);
  }
  for(String path:new String[]{"//other/api","/api/../private","/api/x\r\n"}){boolean rejected=false;try{endpoint.path(path);}catch(IllegalArgumentException e){rejected=true;}check(rejected,"reject request path");}
  System.out.println("Server endpoint HTTPS, canonicalization and injection tests passed");
 }
 static void check(boolean value,String message){if(!value)throw new AssertionError(message);}
}
