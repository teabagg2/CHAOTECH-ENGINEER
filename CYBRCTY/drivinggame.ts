type Ref<T> = { current: T };

type ScenarioType =
  | "stop_sign"
  | "traffic_light"
  | "speed_limit"
  | "turn_signal"
  | "yield"
  | "crosswalk";

type ScenarioData = {
  state?: "red" | "green";
  limit?: number;
  direction?: "left" | "right";
};

type Scenario = {
  type: ScenarioType;
  data: ScenarioData;
  y: number;
  passed: boolean;
  actionCompleted: boolean;
};

type GameState = {
  speed: number;
  carX: number;
  distance: number;
  activeScenarios: Scenario[];
  brakePressed: boolean;
  signals: { left: boolean; right: boolean };
  timeSinceLastQuiz: number;
  activeQuiz: string | null;
  isPaused: boolean;
  lives: number;
  isGameOver: boolean;
  score: number;
};

type KeyState = Record<string, boolean>;

type QuizQuestion = string;

const QUIZ_INTERVAL = 30;
const QUIZ_QUESTIONS: QuizQuestion[] = [
  "What should you do when approaching a stop sign?",
  "What does a red traffic light mean?",
  "When should you use a turn signal?",
];

const stateRef: Ref<GameState> = {
  current: {
    speed: 0,
    carX: 0,
    distance: 0,
    activeScenarios: [],
    brakePressed: false,
    signals: { left: false, right: false },
    timeSinceLastQuiz: 0,
    activeQuiz: null,
    isPaused: false,
    lives: 3,
    isGameOver: false,
    score: 0,
  },
};

const keys: Ref<KeyState> = { current: {} };
const roadOffsetRef: Ref<number> = { current: 0 };

const setGameState = (state: GameState): void => {
  stateRef.current = state;
};

const spawnScenario = (state: GameState): void => {
  const types: ScenarioType[] = [
    "stop_sign",
    "traffic_light",
    "speed_limit",
    "turn_signal",
    "yield",
    "crosswalk",
  ];
  const type = types[Math.floor(Math.random() * types.length)];
  const data: ScenarioData =
    type === "traffic_light"
      ? { state: Math.random() > 0.5 ? "red" : "green" }
      : type === "speed_limit"
        ? { limit: 30 }
        : type === "turn_signal"
          ? { direction: Math.random() > 0.5 ? "left" : "right" }
          : {};

  state.activeScenarios.push({
    type,
    data,
    y: 0,
    passed: false,
    actionCompleted: false,
  });
};

const handleMissedScenario = (
  scenario: Scenario,
  state: GameState,
): void => {
  scenario.passed = true;
  state.lives = Math.max(0, state.lives - 1);
};

const MAX_SPEED = 60;
const ROAD_SPEED_MULTIPLIER = 0.5;

export const updateGame = (dt: number): void => {
  if (!Number.isFinite(dt) || dt < 0 || stateRef.current.isGameOver) return;

  const state = { ...stateRef.current };
  state.activeScenarios = state.activeScenarios.map((scenario) => ({
    ...scenario,
    data: { ...scenario.data },
  }));
  state.signals = { ...state.signals };

  // Accelerate, brake, or coast
  let accel = 0;
  if (keys.current["ArrowUp"] || keys.current["KeyW"]) accel = 20;
  if (
    keys.current["ArrowDown"] ||
    keys.current["KeyS"] ||
    state.brakePressed
  ) {
    accel = -40;
  }

  if (accel === 0 && state.speed > 0) accel = -5;

  state.speed = Math.max(
    0,
    Math.min(state.speed + accel * dt, MAX_SPEED)
  );

  // Steering
  if (state.speed > 0) {
    if (keys.current["ArrowLeft"] || keys.current["KeyA"]) {
      state.carX = Math.max(-1, state.carX - 2 * dt);
    }
    if (keys.current["ArrowRight"] || keys.current["KeyD"]) {
      state.carX = Math.min(1, state.carX + 2 * dt);
    }
  }

  state.distance += state.speed * dt * 2;
  roadOffsetRef.current += state.speed * ROAD_SPEED_MULTIPLIER;

  // Spawn driving scenarios
  if (
    Math.random() < 0.005 &&
    state.activeScenarios.length === 0 &&
    state.speed > 10
  ) {
    spawnScenario(state);
  }

  // Move and resolve scenarios
  for (let i = state.activeScenarios.length - 1; i >= 0; i--) {
    const scenario = state.activeScenarios[i];
    if (!scenario) continue;
    scenario.y += state.speed * ROAD_SPEED_MULTIPLIER;

    if (
      scenario.y > 700 &&
      scenario.y < 900 &&
      !scenario.passed &&
      !scenario.actionCompleted
    ) {
      checkScenarioAction(scenario, state);
    }

    if (scenario.y > 1000) {
      if (!scenario.actionCompleted && !scenario.passed) {
        handleMissedScenario(scenario, state);
      }
      state.activeScenarios.splice(i, 1);
    }
  }

  // Pause for a driving quiz every 30 seconds
  state.timeSinceLastQuiz += dt;
  if (state.timeSinceLastQuiz > QUIZ_INTERVAL && state.speed > 0) {
    state.isPaused = true;
    state.activeQuiz =
      QUIZ_QUESTIONS[Math.floor(Math.random() * QUIZ_QUESTIONS.length)] ??
      null;
    state.timeSinceLastQuiz = 0;
  }

  if (state.lives <= 0) state.isGameOver = true;
  setGameState(state);
};

const checkScenarioAction = (scenario: Scenario, state: GameState): void => {
  let success = false;

  switch (scenario.type) {
    case "stop_sign":
      success = state.speed < 1;
      break;
    case "traffic_light":
      success = scenario.data.state === "red" && state.speed < 1;
      break;
    case "speed_limit":
      success =
        scenario.data.limit !== undefined &&
        state.speed <= scenario.data.limit + 5;
      break;
    case "turn_signal":
      success =
        (scenario.data.direction === "left" && state.signals.left) ||
        (scenario.data.direction === "right" && state.signals.right);
      break;
    case "yield":
    case "crosswalk":
      success = state.brakePressed || state.speed < 15;
      break;
  }

  if (success) {
    scenario.actionCompleted = true;
    scenario.passed = true;
    state.score += 20;
  }
};