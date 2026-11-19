import assert from 'node:assert/strict';import fs from 'node:fs';
import {branches,at,metric,growth,ratio,scenario} from '../frontend/analytics.mjs';
const d=JSON.parse(fs.readFileSync('data/2026Q3.json')),p=JSON.parse(fs.readFileSync('data/2025Q3.json')),s=at(d);
let count=0;const near=(a,b,label)=>{assert.ok(Math.abs(a-b)<Math.max(1,Math.abs(b)*1e-9),`${label}: ${a} vs ${b}`);count++};
near(s.gwp,908554341410.039,'Official 2026Q3 gross premium');near(s.gep,819907012551.9474,'Gross earned premium');near(s.netProfit,90475647022.36914,'MALI69 net profit');
near(s.claim,586361431106.4877,'Gross incurred');near(metric(s,'core'),-67978869762.3002,'Exclude investment transfer');
near(branches.reduce((a,b)=>a+(at(d,'9000',b)?.gwp??0),0),s.gwp,'18-branch reconciliation');
near(d.rows.filter(r=>r.branch==='HAYATDISI'&&r.id!=='9000').reduce((a,r)=>a+r.gwp,0),s.gwp,'48 companies reconciliation');
near(metric(s,'cr'),92.37927,'Combined ratio');near(metric(s,'nlr'),81.3799812,'Net loss ratio');
assert.equal(growth(100,0),null);assert.equal(growth(100,-5),null);assert.equal(ratio(100,-1),null);assert.equal(metric(undefined,'cr'),null);count+=4;
const base=scenario(s,0,0,0,0);near(base.tech,s.tech,'Scenario zero shock');near(base.impact,0,'Scenario zero impact');near(base.cr,metric(s,'cr'),'Scenario baseline CR');
const stress=scenario(s,0,10,0,-20);near(stress.impact,-s.netClaim*.1-s.transfer*.2,'Net claims and investment shock');
near(scenario(s,10,0,5,0).impact,s.nep*.1+s.expense*.05,'Net premium and cost shock');
assert.ok(d.checks.every(c=>c.ok));assert.ok(p.checks.some(c=>!c.ok&&c.name.includes('Dağıtım')));count+=2;
for(const file of fs.readdirSync('data').filter(f=>/^20\d{2}Q/.test(f))){const x=JSON.parse(fs.readFileSync('data/'+file));assert.ok(x.rows.every(r=>r.id&&r.branch));assert.ok(x.rows.every(r=>r.netProfit==null||r.branch==='HAYATDISI'));assert.ok(x.sources.every(s=>s.url.startsWith('https://www.tsb.org.tr/content/Statistics/')));count+=3;}
console.log(`PASS: ${count} financial, scope and scenario checks across 9 periods.`);
