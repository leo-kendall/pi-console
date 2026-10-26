// SPDX-License-Identifier: Apache-2.0
package dev.piconsole;

final class PollGate {
    private boolean visible;
    private boolean inFlight;
    private long generation;
    private long request;
    private long running;
    private long activeGeneration;

    synchronized void enter() { visible = true; generation++; }
    synchronized void leave() { visible = false; generation++; }

    synchronized long begin() {
        if (!visible || inFlight) return -1;
        inFlight = true;
        running = ++request;
        activeGeneration = generation;
        return running;
    }

    synchronized boolean finish(long token) {
        if (!inFlight || token != running) return false;
        inFlight = false;
        return visible && token == request && activeGeneration == generation;
    }

}
