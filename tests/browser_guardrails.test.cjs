/* Run with: node --test tests/browser_guardrails.test.cjs
 * Synthetic only; never use or log real user counseling conversations.
 */
const {test} = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const g = require("../chat-guardrails.js");
const root = path.resolve(__dirname, "..");
const msg = (role, content) => ({role, content});

test("unknown private information remains unknown across turns", () => {
  const history = [msg("user","나 요즘 고민이 있어"),
    msg("assistant","어떤 고민인가요?"),msg("user","뭔지 알아?")];
  const result=g.preflight(history);
  assert.equal(result.category,"unknown_context");
  assert.match(result.reply,/아직.*알 수 없/);
  assert.doesNotMatch(result.reply,/학교|연애|진단/);
});
test("introduces itself as AI without pretending to be a professional", () => {
  const result=g.preflight([msg("user","너 누구야")]);
  assert.equal(result.category,"identity");
  assert.match(result.reply,/AI/);
  assert.match(result.reply,/실제 심리상담사나 의사는 아니/);
});
test("does not replace normal greetings or general conversations with canned replies", () => {
  assert.equal(g.preflight([msg("user","안녕")]),null);
  assert.equal(g.preflight([msg("user","친구랑 싸워서 속상해")]),null);
  assert.equal(g.assess("요즘 힘들어"),null);
});
test("supports direct self-harm and third-party urgent help", () => {
  for(const phrase of ["자살 생각이 들어요","나를 다치게 하고 싶어","오늘 밤 자살할 생각이 있어"]) {
    const result=g.assess(phrase);
    assert.equal(result?.category,"self_harm",phrase);
    assert.match(result.reply,/119|112|109/);
  }
  const third=g.assess("친구가 오늘 죽겠다고 했어");
  assert.equal(third?.category,"third_party_crisis");
  assert.match(third.reply,/119|112/);
});
test("explicit refusal of self-harm is not automatically treated as suicidal intent", () => {
  assert.equal(g.assess("나는 죽고 싶지 않아"),null);
  assert.equal(g.assess("저는 죽고 싶지 않아요"),null);
});
test("imminent harm and dangerous dosing get appropriate human-help guidance", () => {
  assert.equal(g.assess("지금 폭행을 당하고 있어")?.category,"abuse");
  const medication=g.assess("처방약을 두 배로 먹어도 돼?");
  assert.equal(medication?.category,"medication");
  assert.match(medication.reply,/의사|약사/);
});
test("no greeting repetitions and no false clinical credentials in model output", () => {
  assert.equal(g.polish("안녕하세요! 정말 힘드셨겠어요.",[msg("user","나 힘들어")]),"정말 힘드셨겠어요.");
  assert.match(g.polish("저는 실제 심리상담사입니다.",[msg("user","너 누구야")]),/AI/);
  assert.doesNotMatch(g.polish("당신은 확실히 우울증 환자입니다.",[msg("user","우울증이야?")]),/우울증 환자입니다/);
});
test("context instruction avoids re-asking the last question", () => {
  const note=g.contextNote([msg("assistant","친구와 연락을 자주 하나요?"),msg("user","응")]);
  assert.match(note,/반복 금지/);
  assert.match(note,/짧은 동의/);
});
test("client and server integrate the guardrails without remote chat API", () => {
  const html=fs.readFileSync(path.join(root,"index.html"),"utf8");
  const server=fs.readFileSync(path.join(root,"app.py"),"utf8");
  assert.match(html,/<script src="\/chat-guardrails\.js"><\/script>/);
  assert.match(html,/MaumgyeolGuardrails\?\.preflight\(history\)/);
  assert.match(html,/MaumgyeolGuardrails\?\.assess\(text\)/);
  assert.match(server,/if p=="\/chat-guardrails\.js":/);
  const inline=html.match(/<script>'use strict';([\s\S]*?)<\/script>/);
  assert.ok(inline, "inline browser application script is present");
  assert.doesNotThrow(()=>new vm.Script("'use strict';"+inline[1]));
});
