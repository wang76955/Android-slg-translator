package androidx.lifecycle;

public class Lifecycle {
    public enum State {
        DESTROYED,
        INITIALIZED,
        CREATED,
        STARTED,
        RESUMED;

        public boolean isAtLeast(State state) {
            return compareTo(state) >= 0;
        }
    }

    private State currentState = State.STARTED;

    public State getCurrentState() { return currentState; }
    public void setCurrentState(State state) { currentState = state; }
}
