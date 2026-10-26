// SPDX-License-Identifier: Apache-2.0
package dev.piconsole;
import java.util.*;
/** Pure notification candidate and freshness policy. */
final class AlertDelivery {
 static Set<String> candidates(Collection<String> history,Collection<String> active){Set<String> out=new LinkedHashSet<>(history);out.addAll(active);return out;}
 static Set<String> unseen(Collection<String> candidates,Collection<String> seen){Set<String> out=new LinkedHashSet<>(candidates);out.removeAll(seen);return out;}
 static boolean stale(double sampled,double now){return !Double.isFinite(sampled)||sampled<=0||now-sampled>120||sampled-now>30;}
}
