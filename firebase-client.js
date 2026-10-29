/*
 * Maumgyeol account integration. Safe-by-default: if Firebase project is not
 * configured, no auth SDK loads and existing owner access stays unchanged.
 * All user records are written only under users/{uid}/sessions/{sessionId}.
 */
const $=id=>document.getElementById(id);
const gate=$('accountGate'),status=$('accountStatus'),login=$('googleLoginButton');
const historyStatus=$('historySessions'),profile=$('accountName');
let auth=null,db=null,authFns=null,store=null,uid=null;
let currentUser=null,sessionId=null,sessionCreated=0;
let writeChain=Promise.resolve(),connected=false;
const inform=(text)=>{if(status)status.textContent=text;};
const historyMessage=(text)=>{if(historyStatus)historyStatus.textContent=text;};
const currentPath=()=>store.doc(db,'users',uid,'sessions',sessionId);
const newId=()=>globalThis.crypto?.randomUUID?.()||'conversation-'+Date.now()+'-'+Math.random().toString(36).slice(2,12);
const helpText='구글 로그인과 기록 저장을 사용하려면 Firebase 프로젝트에 웹 앱·구글 인증·Firestore 보안 규칙을 설정해야 합니다.';

async function loadAccount(){
  let configResponse;
  try{
    const res=await fetch('/api/auth-config',{cache:'no-store'});
    if(!res.ok)throw Error('인증 서비스 연결 정보를 읽지 못했습니다.');
    configResponse=await res.json();
  }catch(error){
    historyMessage('인증 설정을 확인할 수 없습니다. 현재 상담 기록은 저장되지 않습니다.');
    return;
  }
  if(!configResponse.enabled||!configResponse.firebase){
    historyMessage('구글 계정 연결 준비 중입니다. Firebase 프로젝트를 연결하기 전에는 이 화면의 상담 기록이 서버에 저장되지 않습니다.');
    window.maumgyeolSignature?.setStoredSessions([]);
    profile.textContent='계정 미연결';
    $('historySaving').checked=false;
    $('historySaving').disabled=true;
    $('historyRefresh').disabled=true;
    $('deleteAllHistory').disabled=true;
    $('accountLogout').disabled=true;
    return;
  }
  window.maumgyeolAccount.required=true;
  gate.hidden=false;
  inform('안전한 구글 로그인 서비스를 불러오는 중입니다.');
  try{
    const [firebase,authentication,firestore]=await Promise.all([
      import('https://www.gstatic.com/firebasejs/11.10.0/firebase-app.js'),
      import('https://www.gstatic.com/firebasejs/11.10.0/firebase-auth.js'),
      import('https://www.gstatic.com/firebasejs/11.10.0/firebase-firestore.js')
    ]);
    const app=firebase.initializeApp(configResponse.firebase);
    auth=authentication.getAuth(app);
    db=firestore.getFirestore(app);
    authFns=authentication;store=firestore;
    await authentication.setPersistence(auth,authentication.browserLocalPersistence);
    connected=true;
    $('accountDataConsent').addEventListener('change',()=>{login.disabled=!$('accountDataConsent').checked;});
    login.addEventListener('click',startLogin);
    login.disabled=!$('accountDataConsent').checked;
    inform('구글 계정으로 회원가입하거나 로그인할 수 있습니다.');
    authentication.onAuthStateChanged(auth,async user=>{
      currentUser=user;uid=user?.uid||null;
      account.ready=!!user;
      if(!user){
        window.maumgyeolSignature?.setStoredSessions([]);
        gate.hidden=false;historyMessage('로그인한 뒤 대화 내역을 확인할 수 있습니다.');
        profile.textContent='로그인 필요';return;
      }
      gate.hidden=true;
      sessionId=null;sessionCreated=0;
      profile.textContent=user.displayName||user.email||'내 계정';
      inform('로그인됐습니다.');
      try{await refreshHistory();}catch(err){historyMessage('대화 기록을 불러오지 못했습니다. Firestore 접근 규칙을 확인해 주세요.');}
    });
  }catch(error){
    inform('구글 로그인 서비스를 시작하지 못했습니다. 네트워크나 Firebase 설정을 확인해 주세요.');
    historyMessage('계정 인증 모듈을 연결하지 못했습니다. '+helpText);
    login.disabled=true;
  }
}

async function startLogin(){
  if(!connected||!$('accountDataConsent').checked)return;
  inform('구글 로그인 화면을 여는 중입니다.');
  const provider=new authFns.GoogleAuthProvider();
  provider.setCustomParameters({prompt:'select_account'});
  try{
    await authFns.signInWithPopup(auth,provider);
    inform('로그인에 성공했습니다.');
  }catch(error){
    const code=error?.code||'';
    if(code==='auth/popup-closed-by-user')inform('로그인 창을 닫았습니다. 다시 눌러 주세요.');
    else if(code==='auth/popup-blocked')
      inform('팝업이 차단됐습니다. Safari에서 팝업 허용을 확인하거나 로그인 버튼을 다시 눌러 주세요.');
    else if(code==='auth/unauthorized-domain')
      inform('Firebase의 승인된 도메인에 maumgyeol-ai-chat-2026.onrender.com을 추가해야 합니다.');
    else inform('구글 로그인에 실패했습니다. Firebase 구글 로그인 설정을 확인해 주세요.');
  }
}

const account={
  required:false,ready:false,
  async getToken(){
    if(!currentUser)return null;
    try{return await authFns.getIdToken(currentUser);}catch{return null;}
  },
  async saveMessage(){
    if(!currentUser||!db||!$('historySaving').checked||!window.maumgyeolUI)return;
    if(!sessionId){sessionId=newId();sessionCreated=Date.now();}
    const at=Date.now(), sid=sessionId, created=sessionCreated;
    const messages=window.maumgyeolUI.getMessages().slice(-64).map(m=>({
      role:m.role,content:String(m.content||'').slice(0,2400),at:Number(m.at)||Date.now()
    }));
    const title=messages.find(m=>m.role==='user')?.content?.trim().slice(0,70)||'마음 이야기';
    if(!messages.length)return;
    const path=store.doc(db,'users',uid,'sessions',sid);
    writeChain=writeChain.catch(()=>{}).then(()=>store.setDoc(path,{
      title,messages,createdAt:created,updatedAt:at,ownerUid:uid
    },{merge:false})).catch(()=>{
      historyMessage('상담 내용 저장에 실패했습니다. Firestore 규칙과 연결을 확인해 주세요.');
    });
    return writeChain;
  },
  newConversation(){sessionId=null;sessionCreated=0;},
  async signOut(){
    if(!auth)return;
    window.maumgyeolUI?.clearDisplay?.();
    this.newConversation();
    try{await authFns.signOut(auth);}catch{}
  }
};
window.maumgyeolAccount=account;
function showSessions(sessions){
  historyStatus.replaceChildren();
  if(!sessions.length){historyMessage('저장된 상담 대화가 없습니다. 새로운 이야기를 시작해 보세요.');return;}
  for(const entry of sessions){
    const wrapper=document.createElement('div');wrapper.className='history-session';
    const open=document.createElement('button');open.type='button';open.className='history-open';
    const title=document.createElement('strong');title.textContent=entry.title||'마음 이야기';
    const date=document.createElement('small');
    date.textContent=new Date(entry.updatedAt||entry.createdAt||Date.now()).toLocaleString('ko-KR');
    open.append(title,date);
    open.addEventListener('click',()=>{
      sessionId=entry.id;sessionCreated=entry.createdAt||Date.now();
      window.maumgyeolUI?.loadMessages(entry.messages||[]);
    });
    const remove=document.createElement('button');remove.type='button';remove.className='history-delete';remove.textContent='삭제';
    remove.addEventListener('click',async()=>{
      if(!confirm('이 대화 기록을 영구 삭제할까요?'))return;
      try{
        await store.deleteDoc(store.doc(db,'users',uid,'sessions',entry.id));
        if(sessionId===entry.id){account.newConversation();window.maumgyeolUI?.clearDisplay?.();}
        await refreshHistory();
      }catch{historyMessage('삭제하지 못했습니다. Firebase 권한을 확인해 주세요.');}
    });
    wrapper.append(open,remove);historyStatus.append(wrapper);
  }
}
async function refreshHistory(){
  if(!db||!uid)return;
  const snapshot=await store.getDocs(store.query(
    store.collection(db,'users',uid,'sessions'),
    store.orderBy('updatedAt','desc'),store.limit(70)
  ));
  const rows=snapshot.docs.map(doc=>({id:doc.id,...doc.data()}));
  showSessions(rows);
  window.maumgyeolSignature?.setStoredSessions(rows);
}
$('historyRefresh')?.addEventListener('click',async()=>{
  try{await refreshHistory();}catch{historyMessage('저장 내역을 읽지 못했습니다. 데이터베이스 설정을 확인해 주세요.');}
});
$('accountLogout')?.addEventListener('click',()=>account.signOut());
$('deleteAllHistory')?.addEventListener('click',async()=>{
  if(!currentUser||!db)return;
  if(!confirm('저장된 모든 상담 기록을 영구 삭제할까요? 이 작업은 되돌릴 수 없습니다.'))return;
  try{
    const col=store.collection(db,'users',uid,'sessions');
    for(let attempt=0;attempt<100;attempt++){
      const batch=await store.getDocs(store.query(col,store.limit(100)));
      if(batch.empty)break;
      await Promise.all(batch.docs.map(doc=>store.deleteDoc(doc.ref)));
      if(batch.size<100)break;
    }
    account.newConversation();window.maumgyeolUI?.clearDisplay?.();
    await refreshHistory();
  }catch{historyMessage('일부 기록을 삭제하지 못했습니다. 다시 시도해 주세요.');}
});
loadAccount();
