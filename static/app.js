"use strict";
const $ = (id) => document.getElementById(id);
const token = document.querySelector('meta[name="csrf-token"]').content;
let state = {jobs:[],events:[],counts:{},channels:[],running:false};
let availableChannels = [];
let toastTimer;
function toast(message, fail=false) {
  const el = $("toast"); el.textContent = message; el.className = fail ? "error" : "";
  el.style.display = "block"; clearTimeout(toastTimer);
  toastTimer = setTimeout(() => el.style.display = "none", 4600);
}
async function api(path, data) {
  const options = {credentials:"same-origin"};
  if (data !== undefined) {
    options.method = "POST";
    options.headers = {"Content-Type":"application/json","X-CSRF-Token":token};
    options.body = JSON.stringify(data);
  }
  const res = await fetch("/api/" + path, options);
  const result = await res.json();
  if (!result.ok) throw new Error(result.error || "Request failed (" + res.status + ")");
  return result;
}
function countLines(){
  const lines = $("links").value.split(/\r?\n/).map(s=>s.trim()).filter(Boolean);
  $("line-count").textContent = lines.length + " / 500 URLs";
  $("line-count").style.color = lines.length>500 ? "#ff9fac" : "";
}
function fmtStatus(s){return s.replaceAll("_"," ").replace(/\b\w/g,c=>c.toUpperCase());}
function counts(){
  const c = state.counts || {};
  $("stat-total").textContent = state.jobs.length;
  $("stat-ready").textContent = c.pending || 0;
  $("stat-wait").textContent = (c.awaiting_publish||0)+(c.processing||0)+(c.cleanup||0);
  $("stat-done").textContent = c.published || 0;
  $("count-chip").textContent = state.jobs.length + " jobs";
  $("mode").textContent = state.running ? "● Queue running" : "○ Queue paused";
  $("mode").className = "pill " + (state.running ? "running-pill" : "muted-pill");
  $("toggle").textContent = state.running ? "Ⅱ Pause queue" : "▶ Start queue";
  $("buffer-connection").textContent = state.configured?.buffer ? "Configured" : "Missing key";
  $("buffer-connection").classList.toggle("good",!!state.configured?.buffer);
  $("cloud-connection").textContent = state.configured?.cloudinary ? "Configured" : "Direct links";
  $("cloud-connection").classList.toggle("good",!!state.configured?.cloudinary);
}
function create(tag,cls,text) {
  const e=document.createElement(tag);
  if(cls)e.className=cls;
  if(text!==undefined)e.textContent=String(text);
  return e;
}
function jobAction(job,type,label) {
  const b=create("button","mini",label);
  b.type="button";b.onclick=()=>act(job,type);
  return b;
}
async function act(job,type){
  try{
    if(type==="source"){
      const url=prompt("Direct HTTPS video file URL (.mp4, .mov, .webm):",job.media_url||"");
      if(!url)return;
      const title=prompt("Video title (used on YouTube):",job.title||"New short video");
      if(title===null)return;
      await api("jobs/"+job.id+"/source",{media_url:url.trim(),title:title.trim()});
    } else if(type==="delete"){
      if(!confirm("Remove this queue item?"))return;
      await api("jobs/"+job.id+"/delete",{});
    } else if(type==="retry"){
      await api("jobs/"+job.id+"/retry",{});
    }
    toast("Job updated"); await refresh();
  }catch(err){toast(err.message,true);}
}
function renderJobs(){
  const needle=$("search").value.trim().toLowerCase(), filter=$("filter").value;
  const jobs=state.jobs.filter(j=>(filter==="all"||j.status===filter)
    && (j.source_url+" "+j.title+" "+j.status).toLowerCase().includes(needle));
  const root=$("jobs");root.replaceChildren();
  if(jobs.length===0){
    const tr=create("tr");const td=create("td","empty","No matching videos in the queue");
    td.colSpan=4;tr.append(td);root.append(tr);return;
  }
  for(const job of jobs){
    const tr=create("tr"),td1=create("td"),td2=create("td"),td3=create("td"),td4=create("td");
    const a=create("a","source-url",job.title||job.source_url);
    a.href=job.source_url;a.target="_blank";a.rel="noopener noreferrer";td1.append(a);
    td1.append(create("small","subtext","#"+job.id+" · "+(job.media_url?"Source available":"Needs direct licensed video")));
    if(job.error)td1.append(create("small","subtext",job.error));
    td2.append(create("span","status "+job.status,fmtStatus(job.status)));
    td3.textContent=String(job.post_count);
    const actions=create("div","row-actions");
    if(["needs_source","failed"].includes(job.status))actions.append(jobAction(job,"source","Provide media"));
    if(job.status==="failed")actions.append(jobAction(job,"retry","Retry"));
    if(["pending","needs_source","failed","published"].includes(job.status))
      actions.append(jobAction(job,"delete","Remove"));
    td4.append(actions);tr.append(td1,td2,td3,td4);root.append(tr);
  }
}
function renderEvents(){
  const root=$("events");root.replaceChildren();
  if(!state.events.length){root.append(create("p","muted","No events yet"));return;}
  for(const item of state.events){
    const div=create("div","event"),msg=create("span","",item.message);
    const time=create("small","",new Date(item.created).toLocaleString());
    div.append(msg,time);root.append(div);
  }
}
function render(){
  counts();renderJobs();renderEvents();
  if(document.activeElement!==$("caption"))$("caption").value=state.caption||"";
  updateSelectedChannels();
}
async function refresh(){
  try{state=await api("state");render();}
  catch(err){toast(err.message,true);}
}
async function importLinks(){
  $("add").disabled=true;
  try {
    const result=await api("import",{links:$("links").value,rights:$("rights").checked});
    toast("Imported "+result.added+" videos. "+result.duplicates+" duplicates.");
    $("links").value="";$("rights").checked=false;countLines();
    await refresh();
  } catch(err){toast(err.message,true);}
  finally{$("add").disabled=false;}
}
async function loadChannels(){
  $("refresh-channels").disabled=true;
  try{
    const result=await api("channels");
    availableChannels=result.channels.filter(c=>["youtube","tiktok","instagram"].includes(
      String(c.service).toLowerCase()));
    updateSelectedChannels();
    toast(availableChannels.length+" supported channels found");
  }catch(err){toast(err.message,true);}
  finally{$("refresh-channels").disabled=false;}
}
function updateSelectedChannels(){
  const root=$("channels");
  const current=new Set(Array.from(root.querySelectorAll("input:checked")).map(c=>c.value));
  const selected=current.size?current:new Set(state.channels||[]);
  root.replaceChildren();
  if(!availableChannels.length){
    root.append(create("p","muted small","Click Refresh after connecting YouTube / TikTok in Buffer."));
    return;
  }
  for(const item of availableChannels){
    const label=create("label","channel"),input=create("input");
    input.type="checkbox";input.value=item.id;input.checked=selected.has(item.id);
    const detail=create("span");detail.append(create("strong","",item.displayName||item.name));
    detail.append(create("small","",item.service+" · "+item.organizationName));
    label.append(input,detail);root.append(label);
  }
}
async function saveSettings(){
  const items=availableChannels.filter(c=>Array.from(
    document.querySelectorAll("#channels input:checked")).some(x=>x.value===c.id));
  if(items.length>3){toast("Choose no more than three channels",true);return;}
  const services=Object.fromEntries(items.map(c=>[c.id,c.service.toLowerCase()]));
  try{
    await api("settings",{channels:items.map(c=>c.id),platforms:services,caption:$("caption").value});
    toast("Publishing settings saved");await refresh();
  }catch(err){toast(err.message,true);}
}
$("links").addEventListener("input",countLines);
$("file").addEventListener("change",async e=>{
  const file=e.target.files?.[0];if(!file)return;
  if(file.size>300000){toast("Text file too large",true);return;}
  $("links").value=await file.text();countLines();
});
$("add").onclick=importLinks;
$("refresh-channels").onclick=loadChannels;
$("save-settings").onclick=saveSettings;
$("search").oninput=renderJobs;
$("filter").onchange=renderJobs;
$("toggle").onclick=async()=>{
  try{await api("control",{action:state.running?"pause":"start"});await refresh();}
  catch(err){toast(err.message,true);}
};
countLines();refresh();setInterval(refresh,12000);
