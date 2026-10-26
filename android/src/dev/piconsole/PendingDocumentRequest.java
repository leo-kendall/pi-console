// SPDX-License-Identifier: Apache-2.0
package dev.piconsole;
/** Reject SAF callbacks whose request context was lost on activity recreation. */
final class PendingDocumentRequest {
 static boolean accepts(int request,boolean selecting,boolean metadata){return selecting&&(request==41||request==52||((request==42||request==51)&&metadata));}
}
