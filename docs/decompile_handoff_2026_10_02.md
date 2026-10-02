# Decompile handoff â€” October 2, 2026

Continue on the explicitly authorized `codex/full-decompile` branch. The user
requested sustained useful work until October2 noon America/Chicago,
`2026-10-02 17:00 UTC`. The timed goal and thread heartbeat are active.
At the deadline, finish active validation safely, preserve a reviewable
handoff, push/check the branch and protected work, then pause the heartbeat.
The full game and whole-program accounting remain unfinished.

## Latest scalar path-copy checkpoint

### Actual memmove backward entry validated

The [small backward memmove law](native_movement_memmove_backward_semantics.md)
passes 8,216 independent checks without skips in 48.05 seconds, source GO.
Source fb3d14631725c88ccb0861f527b50fb8e775a8c7a6cb00cc20c44af2039a6c2c;
test 30da52526ec72527c3bea50d4e307e074f56033ad0317cbe60e8e78f39df601d.
All 1,860 complete native cases agree. Both bounded memmove arms now have
separate source identities, literal traces and complete packet laws.
Erase checkpoint395706ac and memmove forward1161df89 pushed. Self80D0
source095e98f2 is sourceGO/native1272PASS; SIMD independent tests in progress.
Fifth independently reconnoiters missing in-buffer assignment7FD0 branch:
owner prefix has11 accesses (register comparisons do not read capacity again),
not initial tentative13; deep frameG-96 and childreturn40802F identified.
No execution gate active. Broader native receipts/accounting remain open.


### Inline erasure validated

The [inline erase law](native_movement_inline_string_erase_semantics.md) passes
2326 independent checks without skips in16.57seconds, source GO.
Source52c24867d833a9cf3852e4f967039a637236fcb0b3d801f1b038fb74c6f77e55;
test8f36ce582a0a7421ac650901c00c67ff36717772606b32521d70f93753f318f4.
All1272native full-state cases agree. Three ownerbranches plus actual36E580
child bind whole14/11/pages/accesses/entrySUBflags/returnstate; canonicallabels
trusted at fixed length. Memmoveforward1161df89/backwardcopyc8109b9a pushed.
Self80D0 Fifthsource095e98f2e9faf6476040b090da9d78b3d1d4509d563ca32ccdf38facfd20d695
frozen; rootnativegatepending, SIMDreview/tests. Root36E580 backwardbinding
fb3d1463/native1860PASS, Fifth independentreview/tests. Rootforward gap geometry
12 additional complete nativecasesPASS (callerstack/return betweenbuffers).
Broader native receipts/accounting remain unchanged.


### Actual erase-child memmove forward entry validated

The [small forward memmove law](native_movement_memmove_forward_semantics.md)
passes4966 independent checks without skips in84.90seconds, source GO.
Sourcecfd10fbf8f438db267fd1e4ace794aa9b6c56cfd4d3f49ab03ab6a8dee4f5df1;
testca51edee10823de1c9ba65b8d4294a13e765e4473ec82c9ae8e158e330151d39.
All1984native full-state cases agree, binding actual36E580 called by8410.
Backwardcheckpointc8109b9a andforward294f0fb3 pushed. Root8410inlineerase
52c24867 sourceGO/native1272PASS; SIMD independent tests. Fifth authors
self80D0 using erase14 with full nested11/boundaries. Root memmove backward
bindingfb3d14631725c88ccb0861f527b50fb8e775a8c7a6cb00cc20c44af2039a6c2c
private/nativegate72797 active; review/tests pending. Larger paths/accounting open.


### Backward overlapping copy validated

The [small backward overlap law](native_movement_small_backward_copy_semantics.md)
passes8216independent checks without skips in56.13seconds, source GO.
Source67548a34a8f6e2c6fa42bf6ec46c603aaf7283643b6798f39dc573c131b74322;
test1e560a03f05fb89e5a14e9f4366ad1ddb7801e44ae8ede47e8172954c5aae752.
All1860 native full-state cases agree. All465 rightward count/shift pairs and
sixteen alignments tested; finalEDX=N is bound separately from forward ABI.
Forwardcheckpoint294f0fb3 pushed; record176e734b pushed. Memmove36E580 source
cfd10fbf/sourceGO/native1984PASS/testca51edee4966 gate running serially.
Inlineerase8410 source52c24867/native1272PASS, SIMDreview/tests; Fifth authors
self-substring80D0 usingactualerase8410child. All13protected unchanged16:33UTC.
Broader native receipts/accounting remain unchanged.


### Overlapping forward copy validated

The [forward copy including overlap](native_movement_small_forward_copy_semantics.md)
passes4966 independent checks without skips in45.44seconds, source GO.
Source8f3ab50576118c3a17be8e1bc0d1b2e4de2790b74480322a47644fdc767bc01c;
test383d18fb2e1cdf5523cdbc9bd2943fd1fe8607049721d4231320b497644e7ffb.
All1984 native self/leftward overlap full-state cases PASS on V2. The prior
disjoint domain is preserved, including buffers straddling stack/return gaps.
Recordcopy176e734b andcheckpointdocse9353ee8 pushed. Backward67548 sourceGO,
1860nativePASS/test1e560a03 frozen8216, gatepending. Memmove36E580 forward
cfd10fbf sourceGO/native1984PASS, Fifth finishing independently relocated tests.
Root inlineerase8410 draft52c24867 nativegatepending; no publication claim yet.
Broader native receipts/accounting remain unchanged.


### General inline-string record copy validated

Checkpoint176e734b pushed. The [inline-string record-copy law](native_movement_effect_record_inline_copy_semantics.md)
passes 780 independent checks without skips in 106.78 seconds, source GO.
Source V3 00d84eeaf36010a6eae6a94488d9706f9d4c604d13b560b5cf7a6d2b8e6d1196;
test a794f74d81f1cae6c528f562cb02e1709f953ed6e87fbb9079fb0e87a24c0ad9.
Eight independent lengths0..15 and path counts0..511 predict full16,
eight string14 packets, complete path15 and every full checkpoint.
Seven mixed native cases agree; V3 only adds an upfront code-page guard to
native-validated V2. Seven V3 all-empty common15 compatibility cases PASS.
Backward-copy67548 has1860native full-state PASS/source GO; SIMD tests.
Root forward-copyV2 8f3ab50576118c3a17be8e1bc0d1b2e4de2790b74480322a47644fdc767bc01c
has1984native overlap full-state PASS (unchanged V1 semantics), Fifth reviews/tests.
V2 preserves prior disjoint stack/return-gap geometry after independent feedback.
No execution gate active. Broader native receipts/accounting remain open.


### Inline substring copy validated

The [inline-string substring-copy law](native_movement_inline_string_copy_semantics.md)
passes1017independent checks without skips in25.05seconds, sourceGO.
Source4e679263cb3b08bb69a4234c905a467ea490632df59db011ec13027a366033b3;
test05ab962053183c4022ea68b57664c5d88a755264e99b9422d46c8715843b40fe.
All128full-state nativecases/sourceLength0..15/offset0endinterior/request0/3/MAX
PASS. Full14/positivechild11/allbytes/access/terminal/prefix joins; canonical
childinstruction labels/trace length trusted explicitly. Assignmentdf774ee0
andmemcpy79fc5a49 pushed; noactiveexecutiongate.
RootrecordinlinecopyV2 55608aa46564d2be682494ccfb0a93cf2490b974f191e1dc44d9758defa623a7
sourcefreeze/native7fullcasesPASS; SIMD independentlyreview/tests.
EightinlineL0..15 +pathN0..511, complete16 (old15 plus8fieldpackets14),
manualfieldprefix/suffix/checkpointpages/ABI/nested11 actualinput joins.
SourceEDXcarry corrected onlynewmodel; oldpublicempty laws unchanged.
Broader native corpus/accounting remain open.


### External inline string assignment validated

The [external inline-string assignment](native_movement_inline_string_assign_semantics.md)
passes2306independent checks without skips in28.72seconds, sourceGO.
Source2612969b9ed907fbb65d057d1b05b30cc6766611085eb79a28113acccbc3712f;
test5c77eda5e60c540497f9dd697f55baaab6437a3bfeacd2444eb295c427498ac8.
Root192standard+18NULL/unmapped/inlinepaddingzero full-statecasesPASS.
Complete13/positivefull11manualmemcpy/snapshot/directpages/types/forgeries,
actualzeroECX/EDXprefixdistinctions andexternalpredicate independentlyclosed.
Memcpycheckpoint79fc5a49 pushed; normalCharge5c521307/Move48e3e92e pushed.
Root80D0 inlinecopy4e679263 sourceGO/native128PASS; Fifth independentlytests.
Rootrecordinlinecopyb7a8ecdd835483f17cefdb26424e43c68adfb547fb9b131db16df4a61881aada
private/unfrozen extends smallcopyto8inline0..15strings/path0..511; nativegate
86868 active. EDXcarry corrections remove oldempty assumptions atpathentry
andlaststring; no public oldlaw changed. Needsindependentreview/tests.
Broader native receipts/accounting remain unchanged.


### Small scalar memcpy validated

The [zero-through31-byte disjoint scalar copy](native_movement_small_memcpy_semantics.md)
passes2117independent checks without skips in17.93seconds, sourceGO.
SourceV2 7e05962f91c75bbdcbc95cc1a6283e396ce6576343ba5746898956c4fe0d1fe0;
test09d9d039cb051d97f0769088565eeb5f026bfb733316e3efdbe6eba38a66a353.
V2onlyaddsprogram-facts provenance; all executabledefinitionssameasV1/native256
full-statecasesPASS. ActualsparseCRTbody12ranges1330B/404points hashedmatch;
40selectedpoints/pointerorder/DWORDandbyte loops/complete11/flagsDF closed.
NormalChargecheckpoint5c521307 pushed, normalMove48e3e92e pushed, all13protected
unchanged. Fifth7FD0 inlineassignment2612969b9ed907fbb65d057d1b05b30cc6766611085eb79a28113acccbc3712f
sourceGO/native192standard+18zero/unmapped/padding casesPASS; SIMDauthors tests.
Root80D0 inlinecopy4e679263 sourceGO/native128PASS; Fifth authors tests.
Noactiveexecutiongate; larger/overlap/SIMD/nativecorpus/accounting remainopen.


### General ordinary normal AddCharge validated

The [normal AddCharge small-path composition](native_movement_addcharge_small_normal_semantics.md)
validates411distinct independent checks, sourceGO. Initial409PASS359.32seconds;
two stale allocation-layout fixtures corrected, unchanged implementation;
36affected geometry/domain checksPASS10.90seconds.
Source44bbf67db18cd260365c27c9b9ad825ab93992b281f3cb5ddc78a3e01246d858;
testV2 6413df6922a0599a3d8434906d5fad5059aa9695aa45ffe8a6c9bced80a60996.
Five complete nativecasesN2K2/N2K511/N3K17/N17K511/N384K511 PASS.
Count384 is conservativefour-buffer artifactDATA geometry, notgamebound;
capacitythrough511, full14/path4,6primary8imports, completecallerfree8.
NormalMovecheckpoint48e3e92e pushed; smallappendf1060a05/copy69a16765/
assignment28ba6c69 pushed. RootmemcpyV2 7e05962f91c75bbdcbc95cc1a6283e396ce6576343ba5746898956c4fe0d1fe0
has256nativecases/sourceGO; SIMD independentlyauthors tests. Fifth authors
inline7FD0 assignment; root80D0 substringcopy4e679263cb3b08bb69a4234c905a467ea490632df59db011ec13027a366033b3
private/unfrozen has128nativecasesPASS, needs independentreview/tests.
Noactiveexecutiongate; broader native receipts/accounting remain unchanged.


### General ordinary normal AddMove validated

The [normal AddMove small-path composition](native_movement_addmove_small_normal_semantics.md)
passes393independent checks without skips in233.96seconds, sourceGO.
Source07dea40594c544ec02cce8f55db1591b29ef72b971edec8f90fe4106e46093c6;
test2fff2997fd1d3b44735ce547ea4eb10ae6df5895df0f0b6923a8578d396185c9.
Five complete nativecasesN2K2/N2K511/N3K17/N17K511/N511K511PASS.
Full14/path4/count2compatibility;16primary6imports; completecallerfree8 checked
beforeRETtransport; COMMON/topchildkeys typed, extra/nestedmetadata trusted.
Smallappendcheckpointf1060a05 pushed, copy69a16765/assignment28ba6c69 pushed.
NormalCharge44bbf67d sourceGO/native5PASS, independenttest3d12ba752609c91106c8a2a852dda0b2f0f969f24566eeb8ff57b9f04cc5435a
is running serially. Rootsmallmemcpy4ad246a4cfdd498d1c7c5e604efebc9aecf4c5e88c069681216595d6f7dfd090
N0..31 has256complete nativecasesPASS; SIMD source/tests review.
Fifth authors external inline-string assignment, no projectexecution in lanes.
No broader native receipt or whole-program accounting promotion.


### General small record append validated

The [external-source small record append](native_movement_effect_record_small_append_semantics.md)
passes670independent checks without skips in251.58seconds, sourceGO.
Source42ffd31bae115454ae652ff61e09ad1aa1ad8580ea0082a3f7bf250f9a4d8e0d;
test43f263c1031535f324cfa58566a86d8241ee924135358f7e41d651d40a1574dd.
Seven full-state native cases0/1/2/3/17/511 and oldcount2full16 compatibilityPASS.
Full record15/path15/7allocator/10scalar closed; width1/2/4 replay,
complete page/prefix/terminal joins, trusted nested metadata scope explicit.
Copycheckpoint69a16765 pushed; assignment28ba6c69 pushed.
Private normalMove07dea405 and normalCharge44bbf67db18cd260365c27c9b9ad825ab93992b281f3cb5ddc78a3e01246d858
both sourceGO/five actual full-state probesPASS; independent suites authored
by SIMD and Fifth respectively. Charge count2..384 is four-buffer12KiB
artifact geometry, not a game limit; original capacity extends through511.
No active execution gate. Broader native receipts/accounting remain unchanged.


### General small record copy validated

The [general empty-string small-path record copy](native_movement_effect_record_small_copy_semantics.md)
passes881independent checks without skips in246.96seconds, sourceGO.
Sourcec7005c462527c95786ee53f782325fdbcab87c98297d4ce9e5bffaa77aef773a;
testfacc1e6889bb36fe8bb2d5a92c623968228d85dbb27df4646800a4580ec4bea3.
Seven actual full-state cases0/1/2/3/17/511 and old empty14/count2full15
compatibilityPASS. Zero20/positive23 states, full path15/allocator7/scalar10,
exact byte replay/prefix page joins, explicit trusted nested metadata scope.
Assignmentcheckpoint28ba6c69 is pushed, protected13unchanged.
Private general normal AddMove V2 07dea40594c544ec02cce8f55db1591b29ef72b971edec8f90fe4106e46093c6
sourceGO and five complete native casesN2K2/N2K511/N3K17/N17K511/N511K511
PASS, trace2029+30N/events1269+12N. SIMD independently authors tests.
Small append42ffd31b native7PASS, Fifth independently authors tests.
No active execution gate and no broader native receipt/accounting promotion.


### Positive small path assignment validated

The [general positive empty-destination assignment](native_movement_path_small_assign_semantics.md)
validates659distinct independent checks, sourceGO. Initial658PASS44.76seconds;
one positive geometry fixture overlapped its stack/source and was corrected
without changing the implementation; seven affected checksPASS1.29seconds.
Source01381a9db05be60f6f3415f7181cc0732c75b77f78154054409784c87ee8456e;
testV2 57924bec7cea24906de02794cdce6d34592bb27f49f24f31420cfff61109b7fc.
Five full-state native probesN1/2/3/17/511 and count-two full15 compatibilityPASS.
General small record copyc7005c46 has sourceGO and frozen independent test
facc1e6889bb36fe8bb2d5a92c623968228d85dbb27df4646800a4580ec4bea3,
881 checks ready for serial execution. General append42ffd31b native7PASS,
Fifth independently authors tests. Root general normal AddMove counts2..511
is private/unfrozen; SIMD reviews source before test authoring. Latestpushed
af320d53. No broader native receipt or whole-program accounting promotion.


### Standalone early AddCharge validated

The [actual-page AL-zero AddCharge wrapper](native_movement_addcharge_early_semantics.md)
passes821independent checks without skips in52.13seconds, sourceGO.
Source5d326a9c8089f300fc309f576bb1356955679cb46725d02d2c3824c7c30dc1ea;
testaf37af42fc52653b4c635a625610a0d3d837999cd62545b5eedeb9eb451d78bf.
Rootfouractualfull-statecasesNULL115/74,ownedempty155/99,one284/177 PASS.
Full14packet, clone15/earlyMove15/trustedclosednestedsemantics, fullmanualouterfree8
beforecheckedRETtransport, callerfourthargumentrewrite and XMM0parambits are
independent. No new record; NULLfinalEAX0 andownedfinalEAX1 accurately differ.
Latestpushedbfdd512d; smallclone594/earlyMove571/smallDestroy605 allpushed.
Private smallrecordcopyc7005c46 native7cases0/1/2/3/17/511/full15N2compatibility
PASS; SIMD independentlyreview/tests. Private assignment01381a9d native5cases
PASS; Fifth independentlyreview/tests. Rootgeneralappend V2 42ffd31bae115454ae652ff61e09ad1aa1ad8580ea0082a3f7bf250f9a4d8e0d
matchessevenactualfull-statecases530/344zero,609+10N/393+4Npositive; N2oldfull
packetcompatible. V1privatepreserved; V2 replayadmits byte/WORD/DWORD writes.
Appendindependentreview/tests remainqueued. Noactiveexecutiongate.

### Small ordinary record destructor validated

The [general inline small-path destructor](native_movement_effect_record_small_destroy_semantics.md)
passes605independent checks without skips in9.54seconds, sourceGO.
Source9c610cd73df36ce5dd82803e56592f3c94803f5608eae3b24c3a814479de862b;
test11b2f5d59861b8581cb7dcca4ac2a940a16335f2d0c6eecc4e225d0d6d20977c.
Exactfull15 remains compatible atNULL/K2N2. OwnedK1..511 usescapacityforfree,
endneverarchitecturalread, fullcapbytespreserve. Nineactualfull-stateprobes
match123/74owned80/46NULL. Full8free join beforecheckedRETtransport,
typed/domain/forgery/detachment/prechildledger expectations independent.
Latestpushed0eda11dc; earlyMove571 andsmallclone594 arecommitted/pushed.
Noactiveexecutiongate. SIMD independentlyreviews/tests earlyCharge5d326a9c
thenpositiveassignment01381a9d; rootnative4and5casesrespectivelypassed.
Fifth authoring smallrecordcopy0..511, nextappend/generalnormalmovement.

### Actual-page early AddMove validated

The [standalone early AddMove law](native_movement_addmove_early_semantics.md)
passes571independent checks without skips in15.44seconds, sourceGO.
SourceV2 278e542377c21b9c162e66b43a92226c1f45b0afb9de4565678d6bca3411d2eb,
testa468d9bf13150907590c0bd347d982b02ec6eaa09fac585dd27d6d2d986e591f.
V2 only makes explicit the inherited owned full-stack-window/error-page
disjointness premise; V1 remains private. Full15packet covers null or owned
usedcount0/1 with capacity1..511, manualfree8 beforecheckedRETtransport,
dynamicTEST(begin)/TEST(cookie)8C5 and actualcookiecomparison. RootV2 repeats
all144oldpackets/fourbroad actual full-state cases successfully. Smallclone
checkpointf61c43bc is pushed. Small record destruction605checks PASS9.54seconds,
nine actual probesPASS; its separate checkpoint follows. EarlyCharge tests
are being independently authored, positive assignment review remains queued.

### Small ordinary path clone validated

The [general small clone law](native_movement_path_small_clone_semantics.md)
passes 594 independent tests without skips in 26.22 seconds, source GO.
Source3099b41e7d0c22875ab48214ea045b72969b3c98a985c1ba2822b8add78afcc3,
testbf329f9f5bc0ef5fb30aab62ee11a2757456bcac0833bbe02fb6f53b8a3075b3.
It covers actual count0..511, full15 packet, zero helper/runtime exemption,
complete allocation7/scalar10 joins and exact state/page preservation. Root
seven native probes and all48 old count-two packets match. Early AddMove V2
also passes571tests in15.44seconds and all144finite/fouractual native probes;
its checkpoint follows separately. Small destructor605 suite is active serially.
Latest pushed074fcb9d; normal native corpus/tests/CLI seals are committed.

### Continuous normal AddCharge validation completed

The [native normal AddCharge proof](native_movement_addcharge_normal_conformance.md)
passes all 172 independent checks without skips in 1,414.06 seconds; source,
CLI and receipt review are GO. Canonical seal
76ede8315ae9f10e431cf5038a140b1bd6fe055526dd8aae4913167794eae1ef,
raw4e0dbcb9baeed611ef33998e30212fd1be253299b525f2af91f1000328b48c1a,
1,309,782 bytes. Both normal native test packets now have independent V3
constructor-attempt ledgers; their four changed workers pass a focused
serial gate in 24.40 seconds, without repeating unchanged corpus checks.
Normal V3 d0dd6544c43814d59f3eaccbf7a7fae81ec19899783990172e914b7e13578cc7;
Charge V3 cfee873d59c9a43b6bdbb7cdabe71d46016bafdc720cb138bd5290b27a7eaf1b.

Private early Charge source5d326a9c8089f300fc309f576bb1356955679cb46725d02d2c3824c7c30dc1ea
is frozen, SIMD independently reviews/tests. Four actual executable probes
match all state across the selected branches, broad frames, high sources,
cookies zero/high-bit and capacities one/seventeen/511.
NULL115/74, owned-empty155/99,
owned-one284/177; all arms load XMM0, AL-zero skips record mode adjustment,
owned outer free leaves EAX one. Fifth authors
general empty-string record copy composing small clone counts0..511.
Private root small record destruction9c610cd73df36ce5dd82803e56592f3c94803f5608eae3b24c3a814479de862b
has independent source GO/test11b2f5d59861b8581cb7dcca4ac2a940a16335f2d0c6eecc4e225d0d6d20977c
605 checks pending runtime and nine actual full-state probes passed.
Positive empty-destination assignment01381a9db05be60f6f3415f7181cc0732c75b77f78154054409784c87ee8456e
is drafted, five native probes passed with count-two whole-packet compatibility;
independent review queued. Small clone passes594independent checks in26.22seconds.
Latest pushed
d71cb1a2d7e4410db6c7381077b293444672ace4; all 13 protected files unchanged.

### Continuous normal AddMove validation completed

The [native normal AddMove proof](native_movement_addmove_normal_conformance.md)
has independent source, CLI and receipt GO and 162 validated checks without
skips. Initial fourteen expensive native/corpus/control/rebuild/CLI checks
passed in the 565.64-second run; remaining 148 passed in 129.77 seconds after
replacing a fixture-specific predecessor check with full typed handwritten
oracle equality. Production and receipt did not change. Test V2 SHA
ca17da02299a97a2a3520f0b9d9ebbbff34a1965433bf6e55b00a74dd1e9864d.
Seal and native totals below remain exact. AddCharge's 172 independent checks
now run serially; its source, CLI and published receipt review are GO, test V2
87027f0d0059850a7ea4bc0493c55e532c88949f17fcdb57f8c79fa82a2cf965.

Private small path clone 3099b41e7d0c22875ab48214ea045b72969b3c98a985c1ba2822b8add78afcc3
matches all 48 old count-two packets and seven actual full-state probes at
counts zero, one, two, three, seventeen and 511. SIMD independently reviews/tests
it. Private actual-page early AddMove 537b542525868bf0c7da99de5b7e6cb1c94414e976953c865477f0ec1cbd63d4
has independent source GO and frozen test a468d9bf13150907590c0bd347d982b02ec6eaa09fac585dd27d6d2d986e591f,
runtime pending. It matches 144 finite packets with corrected TEST mask and four
actual probes covering capacities zero, one, three and 511, broad frames, zero
and high-bit cookies, signed begin and actual Charge continuation. Fifth now
authors the standalone AL-zero AddCharge wrapper privately.
Latest pushed fcd34c9c5ce0fa0cb60d93d5439d9f3a4aa6f44a; all 13 protected files remain untouched.

The [zero-or-positive-count scalar path law](native_movement_path_scalar_semantics.md)
passes339independent tests without skips in9.06seconds, source GO. Source
954bce940708156ac399a28e351c580aeb77d44c47d993dbae9f8d66f66870d5;
independenttestb38e5f6cc71e763e087ab4d8e09fee9469e45cdc197e405151bed22cee62c129.
Zero copies require no source/destination mapping and execute10/6; positiveN
copies execute11+10Ninstructions/6+4Naccesses. Full10packet pages/GPR/XMM/event/
trace/flags/endpoint predictions and strictdomains are independent. Seven
private nativecasesn0/1/2/3/17/131match allstate; n2wholepacket equalsoldlaw.
No published broader nativecorpus/accounting/ownership/gameplay promotion.

Normal movement native receipts are integrated publicly but uncommitted pending
independent tests. AddMove seal1f7f77d9ef362f2b9157cc444b43b1981fd5a1173c35e3788f275c2f73d89f88
binds48/120/100272instructions62064accesses/1152states; sourceV7privateSHA
d49d6a4d783a1b38e449d3b7b51fc4e3d72575169757c89e91b8c3929d9a7967
(only publication wording changed after allruntimechecks). Its162independent
suite is active serially. AddCharge seal76ede8315ae9f10e431cf5038a140b1bd6fe055526dd8aae4913167794eae1ef
binds48/80/110544instructions68448accesses/768states; author9bac1757…f3917,
SIMD independently reviews/tests. Fifth authors ordinary-small path clone
n0..511 with exactallocation/scalar packets; aligned512+ remains separate.
Latest pushed7131f3989360adcabaae0e553d502cf4c2d6c0ea; all13protected unchanged.

## Latest normal AddCharge pure checkpoint

The [selected normal AddCharge law](native_movement_addcharge_normal_semantics.md)
passes369independent tests without skips in287.23seconds, source review GO.
SourceV2 SHA22d90ddaaf4887a5e3977ab9ac1292a8201570a9723353a4786097fc65db2d67,
independenttest1c2cbb3d1444f26eeff0ebf297f9d27a80e4ebd399045b0d33a9ce239bf72f73.
The full14packet predicts2303instructions1426accesses6primary8import states,
4suppliedallocation/free successes, rawparameter/XMM0bits and latestrecordmode2.
Inner selected append source ordering is explicit; valid nested laws remain
trusted. Two actualcontinuous nativeprobes match allstate/pages/events/trace.
Published native corpus, AL-zero wrapper arms, othercounts, ownership and
pawnmovement are separate gates.

Normal pure checkpoint0b7367f6b42dfaa48f03717d000c96b4a1b9da57 is pushed and
remote/protected verified. Rootnormal nativeV5 SHA562a65238eeeb9db1b2c56c49b0134f6d85582ed3e94bb1c3e62b283faab818d
under movement_addmove_normal_native_draft is building its full48recipes and
120controls serially. SIMD reviews/tests it independently; Fifth authors
AddCharge native based on that closedschema template. No fullgame claim.

## Latest normal AddMove pure checkpoint

The [selected normal AddMove law](native_movement_addmove_normal_semantics.md)
now has446distinct independent checks validated without skips, source GO.
Initial suite443PASS/2invalidgeometryfixtures429.01s; corrected36affected
geometry/domain checks6.39s. Legitimate constructor WORD writes are admitted;
unsupported widths3/8 are rejected. Explicit temporary-source >= receiver-end
guard preserves the selected append domain. Public clean-room source V5 SHA
59d1e054344121948e0e88eba7c097a9fb465ffd9350421c2dc1685aa4807201,
independenttest ff04e602392dee112824711ff1712cee3306dc64af6e46470934a6959293622a.
Its full14packet has2089instructions1293accesses16primary6import states,3supplied
allocation successes and3free successes, actual MOVSS bits/cookie checker.
Valid nested child semantics are trusted; full8caller-free checks before RET
transport. Native private harness passes48pure recipes,2exactexecutable cases,
and5selected of120controls; full native corpus and independent tests pending.

Record-copy native checkpoint e92928c306065eb3f52bf6e39792370ca30e02b9 is pushed,
remote synchronized; all13protected hashes unchanged. AddCharge public pure V2
and private independent testpacket are under serial validation; rootcontinuous
2nativeprobes match2303/1426/all6primary8import states. Fifth authors its private
continuous native harness; SIMD independently tests rootnormal native harness.
No full-game, ownership, general-count or gameplay completion claim.

## Latest record-copy native checkpoint

The [continuous two-entry-path record-copy proof](native_movement_effect_record_copy2_conformance.md)
passes155 independent checks without skips in428.71seconds, source/CLI/receipt
review GO. Canonical seal594b01e901b028f23bc8a75857d9ddf775b481b22285bdaca74fe301753f5489
binds48recipes/90controls/28368instructions/17856accesses/1152states/48supplied
allocations requesting768bytes. Full independent corpus observation and all
three CLI commands reproduce the receipt. Raw104314B SHA4c24d3861e840ff247d441adf16d86f5454985f1bbe76212d30008762dd869d3.
OneUc/two starts; all nine bodies execute continuously with complete boundary,
imported and final pages/GPR/XMM/defined flags. No free/opaque/wide/accounting
promotion or ownership/gameplay closure.

Normal AddMove pure V5 now has446distinct checks validated:443 initial passes,
two invalid low-stack append fixtures corrected, then36affected geometry/domain
checks pass6.39seconds. Its pure files are promoted in the next checkpoint above.
Normal native private V3 under movement_addmove_normal_native_draft awaits root
runtime and SIMD review/tests:2089instructions1293events16primary+6import states,
3suppliedallocations/3frees,20bodies/1206sites/3727bytes. AddCharge pure V2 under
movement_addcharge_normal_model_draft matches two private continuous native
cases2303/1426/all6primary8imports; Fifth independently reviews/tests it.
Full game remains unfinished. Protect all13 original files and run gates serially.

## Prior durable state

The [October 1 handoff](decompile_handoff_2026_10_01.md) records the actual
factory receiver through four native callbacks and standalone installed-copy,
SIMD resize and SIMD growth ingredients. Starting HEAD/remote was
`97752b967b7335b94536c4a52561ab84e5bc4525`; `git pull --ff-only` reported
already current before this tranche. User branch authorization supersedes the
general `main` rule. Agents inherit the primary model; do not use Astra.

## Class append over the SIMD growth child

[Documentation](native_lua_class_simd_vector_return_conformance.md): the
existing-key class operation now grows full4/cap4 to capacity6, allocates48,
copies32 through the actual retained-feature MOVDQU path, supplies successful
old32 free, appends the external record and returns normally. All288 native
cases preserve full pages, old32, tree/key/padding bytes and fresh spare8.
Source/destination equal canonical sets have zero through seven nodes,
1,008 existing-key updates and no tree allocations. There are288 successful
vector allocations and288 free requests under explicit supplied API premises.

The class independently checks the complete18-field growth packet, including
all buffers, ordered memory events, flags/mask/DF, eight GPRs/eight XMMs,
geometry, metadata and both child entry boundaries. Exact vector/fixture
schemas are closed. Native wide accesses are permitted only for the four
selected MOVDQU sites within old32/new32. Growth's installed return is
`0x006eb205`; class/caller return and cookie are checked independently.

Canonical SHA `f0ffcae4eec8beab14a2a24a6b6ecdd736ed523c39ea681ead624e4a7b98008f`;
file SHA `b9219218daa5519c7d2b5cb546b9bccab3491afa72bdfd3d8926714731d32500`;
293,348 bytes. Loaded939 sites/2,440 bytes; executed384. Twelve intended
controls reject ancestor/source/payload/vector/iterator, heap request/response,
free pointer, old storage, XMM, spare8 and cookie corruption. Cookie mismatch
stops at the first failure frontier. No ownership/accounting promotion.

Focused validation:130 passed, no skips, with eight isolated native boundaries,
all controls and exact CLI build/verify/structure. Full288 native replay
reproduced the same receipt after strict-domain/full-child-join fixes.
Unchanged growth/resize predecessor regressions:258 passed, no skips,
388 combined. Independent final source review:GO.

## Logical fifth callback

The [source-backed plan](native_lua_class_factory_callback_fifth_frontier.md)
requires actual fourth-state capture for every producer, including eight XMMs,
flags/DF, all retained pages and independent capture guards. Candidate fifth V
is DATA+0x2800+a on retained page2; old fourth V is DATA+0x3800+a. First8 at
DATA+0x2000+a, second16 at DATA+0x1000+a and third24 at DATA+0x800+a remain
disjoint. Do not replace retained page2 with generated filler.

The [fifth logical model](native_lua_class_factory_callback_fifth_semantics.md)
is integrated. Its exact17 inputs preserve prior
packets, source7/destination8 and omitted key16, old8/16/24/32, full48/spare8,
U13/P24 and both normal returns. Shared operation/callback extensions require
an explicit exact full4/cap4 opt-in; old defaults must stay unchanged.
Stack exclusion is `[T-188,T+8)` with explicit entry bounds188 through
0xfffffff8. Its203 new tests and383 predecessor/shared regressions pass,
586 combined without skips; independent final source review is GO.
Durable checkpoints are `e4f2fec5` (class SIMD join) and `86a8207b`
(exact fifth logical model and full stack guard). Both were pushed and checked
against the remote before the native fifth tranche.

## Actual retained fifth callback

The [fifth native receipt](native_lua_class_factory_callback_fifth_conformance.md)
now proves all216 selected producers through five explicit host invocations,
with actual eight-XMM/full-EFLAGS/GPR/PC captures at every fourth entry/return.
Complete captured pages are checked independently before exactly36 declared
caller/source bytes are patched. The factory-only adapter binds source7/
destination8 and full4/cap4 to the standalone SIMD class join without creating
replacement pages or widening old domains. Fifth grows to capacity6, copies32,
frees old32, appends8 and preserves spare8. All164 controls reject.

Canonical SHA `92dea33a6ca68214a08f9056ef1d6abb0ed7f6450fec789bcb85a2677db70255`;
file SHA `11b70e8b0ee7e061ed4642d4ea1b20d5b57137f65f05ec8d41a531383c190226`;
392,703 bytes,45 pins. Loaded1,134 sites/2,973 bytes; executed900, fifth553.
Partition76/726/27/71/234. Actual factory and all first-fourth observation
hashes/site sets equal the sealed predecessor. All eight XMMs and clear DF
are checked at parent/class/growth/resize/copy/API/cookie/full-return joins;
only four MOVDQU sites admit their exact ordered eight-byte halves.

The new197-test gate and unchanged standalone class130-test gate pass,
327 combined without skips. Exact fifth CLI build/verification/structure
reproduce the deterministic seal. Independent final source/tests and published
receipt reviews are GO. Fourth native default CLI build, verification and
structure gates reproduce its unchanged359,299-byte receipt after the shared
machine plumbing changes. All13 protected user hashes remain unchanged.
No ownership/accounting or whole-game promotion.

The native fifth checkpoint was pushed as `e96c7579577dd2461d2385afabadaf7eb9df932a`;
local HEAD and GitHub were synchronized at that commit before the sixth work.

## Logical sixth spare callback

The [sixth logical model](native_lua_class_factory_callback_sixth_semantics.md)
is integrated. Its exact20 inputs reconstruct first-through-fifth and reuse
the fifth vector: size5/cap6 becomes size6/cap6 with no copy/allocation/free.
Existing40 and earlier8/16/24/32 buffers survive; append8 fills capacity48.
Strict predecessor routing/view guards reject typed aliases, divergent views
and coordinated omitted-key changes before sixth consumes them. Seven existing
routes retain destination8 and omitted16, with no new tree allocation.

The shared callback's separate Boolean `allow_sixth_spare` requires exactly
size5/cap6 and excludes `allow_fifth_growth`; existing operation domain and
callback defaults remain intact. Class writes only U+8, normal writes U+0/U+8;
U17/U16 preservation includes established U13, and P24 remains intact.
Source-derived stack exclusion is `[T-140,T+8)` and class EDX is successor
slot `T-60`.176 new tests plus586 predecessor/shared regressions pass,
762 combined without skips. All16 adjacency/overlap boundary cases pass after
the test helper was corrected to retain the moved userdata's closure identity.
Independent final source review is GO. This is logical evidence, not an actual
sixth callback or XMM/DF proof.

The pure sixth checkpoint was pushed as `eb94cfb4bc7fa43f650b2bac98e81a4e03455088`.
Local HEAD and GitHub were synchronized and the branch pulled before native
sixth changes.

## Actual retained sixth callback

The [sixth native receipt](native_lua_class_factory_callback_sixth_conformance.md)
now executes216 producers through six callbacks and211 rejecting controls.
Every fifth entry/return captures eight actual XMMs/full flags/GPRs/PC; the
fifth return's nonzero XMM0/1 are independently derived from old32. Complete
retained pages and typed allocation/free packets are checked before exact36
caller/source byte patches. The separate `XMM_SPARE_FACTORY` adapter has exact25
fixture/20 vector keys, constructs no pages and independently checks seven
payload writes plus the19-event append/cookie tail. Earlier tree-prefix reads
remain inherited from the sealed oracle.

Sixth preserves old40, appends8 and fills capacity48 with no heap/copy/free,
tree allocation or wide access. All eight XMM registers and DF0 survive each
selected machine join. Class EDX is T-60; stack exclusion [T-140,T+8) and both
normal ABIs match the independent logical model. Source-backed full growth,
resize/copy/allocator/free range exclusions bind the sixth trace. First-five
hashes/site sets, factory hash and fourth-boundary hash remain unchanged.

Canonical SHA `cdd92b83335043ca08b33f04dc4ca9a3643e97f594f8ba8349f40de81f547c18`;
file SHA `f969840a607bf858ae0dedf52bc7140097567c5edadde42ae373fd5e9aff4aac`;
405,953 UTF-8 LF bytes and46 pins. Loaded1,134/2,973 bytes; executed900;
sixth347; partition76/726/27/71/234 unchanged. Sixth487,944 instructions,
1,512 payload updates,10,368 live/capacity bytes,8,640 preserved bytes and216
actual entry/return captures/XMM preservations. Across six callbacks53,136 Lua
requests,2,592 marker/table calls each and1,296 assignment requests; old864
free and SIMD read/write totals remain unchanged.

All136 conformance checks pass without skips, including103 pure and16 isolated
actual checks, sealed-receipt/source mutations and exact CLI rebuild,
verification and structure verification. Independent final source/test and
published-receipt reviews are GO. Shared fifth transport's65 focused pure
regressions pass,201 tests combined; all13 protected hashes remain unchanged.
The complete native sixth tranche was pushed as
`39a774a0c9821ae6fec992f6ca7cb2a2719c183e`; local HEAD and GitHub were checked
equal, protected hashes remained unchanged and pull reported already current
before assertion-dispatch integration. No whole-program accounting or
full-game promotion.

## Next semantic frontier

Prefer assertion-parent dispatch at RVA379cc2: it always passes mode3 into
the first native getter (VA008b7534), calls the second getter (VA008b7318)
only for first result0, and selects alternate iff first==1 or first0/second1.
Execute both native getter bodies and stop before opaque third379550/fourth
379b31 child entry. Independently check stack, arguments, all GPRs/defined
flags, full pages and no global writes. The normal branch passes the original
caller return as an extra fourth argument. Private source-only model/tests
were source-reviewed under `.local_decompile/oct2/assertion_dispatch_draft/`.
The [logical model](native_assertion_helper_parent_dispatch_semantics.md) is
now integrated;254 tests pass without skips. Both explicit typed inputs and
actual-Q page adaptation retain exact getter frames, branch arguments,
CMP/CD5 or TEST/CC5 flags, ordered source-RVA accesses and complete pages.
Incoming flags need only be typed uint32/DF0; AF is not synthesized. Invalid
32-bit stack geometry is rejected before reading its caller words. Source
review is GO. This is logical evidence, not native execution.

Root's source-reviewed private standalone native harness/CLI are under
`.local_decompile/oct2/assertion_dispatch_native_draft/`: exact three bodies
72+63+6 bytes/54 sites, four pinned receipts and2352 vectors combining seven
getter values each,16 alignments and three caller/flag profiles. It executes
all selected bodies in one Unicorn instance and stops at opaque child entry;
checks all eight GPRs/defined flags, exact mode3/getter frames/counts/arguments,
full ordered accesses with RVAs and complete pages. Its19 controls include
15 machine mutations and four event/path-record mutations. Fixture override
was removed, and source errors normalize to the declared ConformanceError.
The harness is now integrated and its full native build passes. Published
canonical SHA `88c1e3a7c73d276650c41cd5f356d7bc72c46c410e35ef84f50aac3ad0d3c5ed`,
file SHA `5f80732d1f6fc73cbf89f19a832a2eb44405335d3dbc76f52b6f46130d7e5a20`,
288,103 bytes. All2352 cases and19 controls pass; alternate384/normal1968,
second-getter336,39 executed sites/71,184 instructions. All99 native
conformance and254 logical tests pass without skips,353 combined, including
exact CLI rebuild/verify/structure. Independent final source/test and
published-receipt reviews are GO; all13 protected hashes remain unchanged. See
[native assertion dispatch](native_assertion_helper_parent_dispatch_conformance.md).

After standalone dispatch closure, join the actual callback assertion prefix
in the same Unicorn instance using a new composed runner. Reuse its fixture,
oracle and Lua controller, validate/capture the complete actual intermediate
boundary, then continue without reseeding or replacing pages. Preserve the
old prefix observation projection/hash and stop at opaque callee entry after
the parent CALL. Failure handling, dialog/abort/INT3 and unwind stay excluded.

The standalone native dispatch was pushed as
`8f8bf73e20d17575e280d10af5d02c4cd8a5b660`; local and remote HEAD matched,
all13 protected hashes survived and pull was already current before the join.
The [continuous callback dispatcher](native_lua_class_callback_assertion_dispatch_conformance.md)
is now integrated: all768 cases and40 controls pass with the old192-prefix
aggregate unchanged at `49e83a1601e72244d5cfab28d2e059ee2bdeb135dbce5687acb01183fd6fccc8`.
One actual machine validates/captures full prefix state, then falls through
without replacing pages or registers. Canonical
`f6693e3b32ec3776e6b1193e582af68f4df77d6178a864e5cffb545eeaff11ce`, file
`efea61a5c1bf67e737c2e31ecc2a49bba01bb667f90f5cfbff4c5414e34c693f`,
117,006 bytes/9pins/5ranges/326bytes/119loaded/98executed. Native instructions
33024prefix+24192dispatch=57216; normal/alternate384each, second384,
Lua requests2880 andmarkers576. All114 tests pass without skips, including74
pure checks,16 isolated actual captures, all40 controls and exact CLI
rebuild/verify/structure. Independent source/CLI/test and published-receipt
reviews are GO; all13 protected hashes remain unchanged. Neither opaque child
instruction executes.

The other distinct next tranche is installed48-byte SIMD-plus-scalar-tail copy
and full6-to-cap9 growth: request72/copy48/freeold48/append8/spare16. Existing
fixed32/old4 receipts must remain unchanged; do not infer the new copy's EDX
from current32's zero return. Avoid further count-only callback expansion.

The source-only48 recon is `.local_decompile/oct2/simd48_recon/HANDOFF.txt`:
the broad native4992-copy matrix actually omits length48. Its exact installed
path is69 instructions/51sites,26 events: eight MOVDQU half hooks followed by
four scalar pairs. EDX at copy return is originalDWORD(old+44), XMM0/1 are
originalfirst32, XMM2..7 survive,flags44/mask8C5 with AF unclaimed and DF0
checked separately. Fresh standalone48 draft under
`.local_decompile/oct2/installed_simd48_draft/` is in progress; source material,
not execution evidence. Its finite48 cases couple16 stack/buffer alignments
with3 distinct profiles and use freshDATA4800 disjoint from retainedDATA2800.
HeapFree's actual frame has handle/flags/pointer, no byte-count argument;
logical old48 capacity must not be mislabeled as a native API size word.

The continuous callback join was pushed as
`063079ece865ac752b014cf5e42864804e62843d`; local/remote HEAD matched and
pull was current before installed48 integration. The
[installed48 copy](native_installed_simd_copy48_conformance.md) now passes its
full48-case/31-control native build and48 pure preliminary checks. It proves
the scalar-tail EDX sentinels, XMM preservation, exact69-site-occurrence path
and26 normalized access events, without changing the old4992 matrix.
Canonical `cc7ba0512777a3d8ed06c5c720857d364296935fcaeb703ca9221938c7ca7cf7`,
file `fcd21af5a4e69983dc9d3c91763e4ccd2c7f3c283705c8f46aa692e41f5db94b`,
21,299 bytes/3pins/169loadedbytes/59loaded/51executed. Native totals3312
instructions/2304copybytes/1248events,192 each wide/scalar reads and writes.
All80 tests pass without skips, including48 pure checks,16 isolated actual
captures, all31 controls and exact CLI rebuild/verify/structure. Independent
final reviews are GO; all13 protected hashes remain unchanged.
The separate [ordinary resize6-to9](native_simd_vector_resize6_to9_conformance.md)
now passes its full48-case/30-control native build. One machine executes
allocation72/copy48/freeO and writes header[D,D+48,D+72], retaining old48 and
spare24. Canonical `009f36e1b254058ec21f7af157f6e86ebfa18039abe24fce1690f9df97bc2949`,
file `4c879a5946aae052b6644fd310be248aaa3caeb8e8eca39a656c423f7a533982`,
54,344 bytes/9pins/249loaded/660bytes/179executed/9456instructions/4992events.
The actual copy-return capture verifies the final scalar EDX before the free
guard overwrites it. SAR3 defines only maskC5 at free entry; AF/OF are unclaimed.
The unchanged allocation oracle is narrowly transported from canonical pointer
06000800+a to actualD only in relation.result/EAX/ECX, with all seven packet
fields checked first. The native allocation-return boundary proves actualD.
All115 focused tests pass without skips, including the handwritten full48-vector
page/event/ABI law,16 isolated actual captures, all controls, source/receipt
mutations, direct code tampering and exact CLI rebuild/verify/structure.
Independent production-source/CLI and published-receipt reviews are GO.
The finite resize checkpoint was pushed as
`fbc6b0b26fb431b7f2f9b94096e130acd688de7a`; local/remote HEAD matched and all13
protected hashes survived. The [actual-page resize adapter](native_simd_vector_resize6_to9_semantics.md)
is now integrated and its87 independent pure tests pass without skips. It
consumes actual pages/H/R/GPR/XMM/flags/installed006eb66e return, never a
transplanted fixture. Complete18-field child packets and all104 events/full
pages are independently checked. Arbitrary source/destination/header page
crossings and O7FFFFFF0 signed-boundary SUB flags804/8D5 are covered.
Independent production-source review is GO; this is logical evidence only.
Private continuous growth6-to9 source/tests are in progress under
`.local_decompile/oct2/growth6_to9_draft/` and `growth6_to9_tests/`; root source
equations are `.local_decompile/oct2/growth6_to9_recon.txt`. Prefix8 events
install resizeR=G-20 with request9 and CMP9vs7 flags0/8D5; child104 and suffix4
give116 events, protectedstack[G-96,G+8). The next machine must capture actual
resizeentry/return and continue without reseeding. No growth/class/seventh
callback native proof yet at that source-only checkpoint.

The actual-page resize adapter was pushed as
`0a438b553f7aef12bb17cd7fbb1e5586d8bdf712`; local/remote HEAD matched and pull
was current before continuous growth integration. The
[continuous growth6-to9](native_simd_vector_growth6_to9_conformance.md) now seals
all48 cases and43 controls,39 machine mutations and4 injected records.
Canonical `23eeb7708d498a7f0187b6031835c07d62e6ec99e27326734460808edaceaf25`,
file `777279d377fb0cfe9447076aac11bbe230f85d4e5fcc8e0cb11595e11fe155e3`,
63203bytes/11pins/289loaded/754bytes/217executed/11280instructions/5568events.
All107 focused tests pass without skips in302.90seconds, including16 isolated
actual captures, complete imported ABI packets, intended controls, exact
rebuild and three CLI commands. Independent source/CLI and published-receipt
reviews are GO. The next class join needs an actual-page growth law with
arbitrary unused[G+4] and return006eb205; no class/seventh-callback proof yet.
Before broadening that law, audit the actual resize model's incoming flags:
arbitrary DF-clear words may include special execution-control flags. Narrow
the declared ordinary flags domain rather than claiming their preservation.
That audit is now complete: onlymaskAD7 with fixedbit1 set is admitted, DF0
checked separately. All117 independent actual-page tests pass without skips;
all61 focused growth logical-composition regressions pass. Independent source
review is GO. Native202/246 stay admitted; old receipts remain unchanged.
Continuous native growth was pushed as
`0ca4b90c3230d1686a14b376e5685358d2b086ef`; the flags correction was pushed
as `29a0e8b916030b05064ca76745ffe85b37dba1fa`. Local/remote HEAD matched and
pull was current before actual-growth integration. The
[actual-page growth law](native_simd_vector_growth6_to9_semantics.md) now passes
all295 independent tests without skips in18.84seconds. Its full21-field packet
preserves arbitrary unused caller words, arbitrary admitted H/G and return
006eb205; all128 ordinary flags project raw2/202 into the actual resize.
Complete child18/lower7-10-8 laws,116events/235trace, signed/crosspage/endpoints,
typed aliases and coordinated forgeries are checked. Source review is GO.
Root also compared all48 finite native packets to this adapter with exact21
equality. Broader native conformance is not inferred. Private class6-to7
native harness/tests are in progress under `class6_to7_draft/` and
`class6_to7_tests/`. Distinct movement-name/builder/parent source research is
under `.local_decompile/oct2/movement_source_plan.txt`; no movement native
execution or public semantic promotion yet.

The continuous [class six-to-seven append](native_lua_class_simd_vector6_to7_return_conformance.md)
now seals all288 native cases and60 controls, with independent source/CLI and
published-receipt review GO. Canonical
`9103e9dd655eaeb9530b0c09f2ea2d050e6e5462c2f796ce3136e63264ff37e6`,
file `e0e0593001657ac09f32fd342c0ed30b21291db6ddf191a6780ef5993061bc60`,
298913bytes/20pins/939loaded/2440bytes/398executed/376956instructions/171252events.
One machine continues the existing-key tree prefix through actual growth
entry L-44/headerU+4/return006eb205, resize L-64, copy48/free-old48, append8
and normal return. Final header[D,D+56,D+72] preserves spare16; all10 actual
boundaries and both imported ABI packets are checked. The97 focused tests
pass without skips:96 in the full704.08s gate, then the receipt test in16.21s
after normalizing legacy end_rva against exclusive_end_rva. No production or
receipt change was required for that test correction. Whole-game accounting
and the seventh factory callback remain open.

Class checkpoint was pushed as `213f044fc8983d5b3340dc3e27fe3739210d30fa`;
local/remote HEAD matched and all13 protected hashes remained unchanged.
The selected [static AddMove/AddCharge binding](native_movement_effect_binding.md)
now seals canonical `54c060913d61f6bb5e4c1f2586f0d5186ea73ad6c058dd48b1cc056e64a410b9`,
file `8dcab678554d5baa3d62ed79ddf51f861cdd13ea3608a08eb5ef670e6bafd86b`,
92129bytes/one program-facts pin. All130 focused tests pass without skips in
207.49seconds, including selected-source rebuild/mutations and all3 exact CLI
commands. Independent source/CLI and final receipt review are GO. The selected
initializer recipes, two20-byte builders and both parents have220nodes/226edges,
without runtime publication or child-semantic claims. BL assignment/AL-copy
facts deliberately avoid a return-value guarantee across opaque child calls.
The private `movement_early_return_draft/` is being authored for144 finite
AddMove null/empty-owned/one-point early paths. Root has only two private null
smokes so far; no public movement native conformance yet. Parameter/SSE,
record construction/path-copy/append and gameplay effects remain open.

The selected movement binding was pushed as
`cf18e2ea7349d456d1758dabd75c9a3fc5ae2660`; local/remote HEAD matched and all13
protected hashes remained unchanged. The private AddMove early-return build
now passes144 native cases/40controls, canonical
`c2448f75dc5c50f3e4de7f6bc0f412016cdb07bbe7becc491d5bd1b31f840079`,
file `45374aa188fd76730c0a2c46e16a8762baf9d1046755472684b73ef9cd6ac2fc`,
43401B/5pins/128loaded/401B/82executed/9888instructions/6000events/96frees.
Primary144pure/9native/all40controls gates pass; independent source/CLI review
is GO. The [public AddMove gate](native_movement_addmove_early_return_conformance.md)
now passes all89 focused tests without skips:77 full-gate checks and12 actual
captures after observer CPU setup was corrected. Production/receipt unchanged;
independent final source/CLI/receipt and observer-fix reviews are GO. Attach
observers after CPU selection and before mapping/execution.

The [default record actual-page law](native_movement_effect_record_default_semantics.md)
now passes302 independent pure tests without skips in6.89seconds, source review
GO. It checks308-byte defaults/183written/125preserved, seven empty-string
helpers,217events/356trace,14complete boundaries, all128 ordinary flags and
arbitrary argument/pages/GPR/XMM/return. It has no normal cookie-check call.
The next private native constructor harness is under
`.local_decompile/oct2/movement_constructor_native_draft/`, with independent
tests being authored in `movement_constructor_native_tests/`. Primary96pure,
10native/all29controls and full96-case builds pass. Private canonical
`942fc246105c941a46ac73e7be432acdacad1428322888b76c0164aca49e673f`,
file `ef954c1f8bdd1672d4b1fd72cf2717f02b93bd9608f9306b987d3ab94bb23c1a`,
57864B/2pins/259loaded/914B/164executed/34176instructions/20832events.
The [public constructor native gate](native_movement_effect_record_default_conformance.md)
now passes all173 focused tests without skips in79.27seconds, including12
independently hooked actual captures/all14 physical boundaries, full96
observation-hash derivation, all29 controls, code/model/source/receipt guards
and exact rebuild/all3 CLI commands. Independent final source/CLI and receipt
reviews are GO. Scope wording was corrected source-above to source-below
before publication; observation hashes and counts stayed unchanged.
Copy/path/append/destruction/AddCharge/gameplay and whole-game accounting open.
The actual-page default model was pushed as
`d19e6c736550f685cfe6ac958feb938435876fa3`; AddMove short paths were pushed as
`f8c0058749539649505034a34029526ddad7709f`. Both remote/protected audits passed.

Next private source work: root authors empty80D0 string-copy model/harness
under `movement_empty_string_copy_draft/`; independent reviewer
simd_class_review_oct2 waits for the frozen interface. Fifth_model_oct2 authors
continuous09A8E0 two-record path clone under `movement_path_clone2_draft/`.
Source-derived clone prediction136instructions/83events/440loadedbytes;
reserve returns only AL1 with preserved high EAX bits, final parent flags are
ADD-stack flags. Existing ordinary allocation pure packet admits count2 but
old native allocation corpus lacks it; the new same-machine composition must
prove actual16-byte allocation, scalar copy16 and all actual boundaries.
No descendant/native gates have been run for either new copy tranche yet.

## Environment and protected work

The [inline record destruction law](native_movement_effect_record_destroy_semantics.md)
is sourceGO and has501 independent checks validated (initial500PASS/1fixtureFAIL
20.93s; padding testmodifieddeclarednulltriple, all2affectedchecksPASS2.81s after
isolatedtestfix). ModelV2 1dd3b2a74a8dbf48859769f8b0293ca06d301cdce51b3ae39adae89db77fc09c
narrows SARmaskC5, full15/null80-46/owned123-74/free8/import39/fullpages agree.
Append pushedcd80a67edca6e268650a3ce9e65cd6db9eb7ce0c; remote/protected verified.
RootnormalAddMove private modelV3 cfe3829678369598a0df6520c64aae32b38104e697b682622dbfe09987e21478
matches2nativecontinuousprobes2089instructions1293events16primaryboundaries/
6imports/fullpages/GPRXMM/parameter. Threealloc16 andthreeHeapFree1 supplied;
noownership/gameplayclaim. Independentnormalpuretests in progress.
Recordcopy2native f23728ab sourceprovisionalGO/all48purepreflightsPASS;
root9smokes/all90controls active while independentnative tests are authored.
No normalAddMove/AddCharge/gameplay sealing yet.


The [no-growth external-source append law](native_movement_effect_record_append2_semantics.md)
is sourceGO and has370 independent checks validated: initial368PASS/1FAIL53.68s
had a positive fixtureOFFFFFFEF inside GFFFFFFF7's protectedstack. Production
rejection was correct; fixture movedO20000FF8 and added separateordinary-stack
maxOcase, all7affectedgeometrychecksPASS2.16s. Full16/629/401/25/header/caller/
fullpages and lower packets agree. Assignment pushed997a443c783a31039d67a30c7ab218766e197f9a,
remote/protected verified. DestructorV2 independent review corrected free-entry
SARcount3 mask8C5 toC5 (OFundefined); four nativeprobes stillPASS80/46null or
123/74owned/fullfree/import/pages, model1dd3b2a74a8dbf48859769f8b0293ca06d301cdce51b3ae39adae89db77fc09c.
Independent destructor tests in progress. Root prepares continuous normal
AddMove prototype from exact20bodyselectedsource; native recordcopy2 author
works separately. NormalAddMove/AddCharge/gameplay remain unsealed.


The [empty-destination path assignment law](native_movement_path_assign2_semantics.md)
is sourceGO and passes381 independent tests without skips in13.96s.
All15 fields162instructions90events7boundaries/import and complete7/10 joins
are predicted. Four private native probes agree includingactual6573A7 stop.
Recordcopy2 pusheda99518a49a58b2db7b093c99167a4e909c389024, remote/protected
verified. Fifth authors continuous recordcopy2 native harness under
movement_record_copy2_native_draft (48cases/591/372/24snapshots/oneHeapAlloc);
SIMD independently tests appendV2. Root destructor private probes4PASS:
80instructions46eventsnull and123instructions74eventsnonnullcount2,
full2freeboundaries/import/fullpages/GPR/XMM and finalraw287. Pointanchor
3785fc3e1f910c8db00b832cd5d2dbfec09eb18d476ca6b3ab10ff5b278acf3f,
204sites656loadedbytes; suppliedHeapFree1 is not ownership/unmapping proof.
Destructor independent closure and normalAddMove/AddCharge remain open.


The [two-entry record-copy pure law](native_movement_effect_record_copy2_semantics.md)
is sourceGO and passes377 independent tests without skips in82.92s.
V2 SHA573197929c2a8715d36bc8121f7ece29626c23f0d533b3871ac2f9b9a0eec1c2
rejects returns inside path buffers and typed child aliases; it explicitly
trusts complete nested clone internals instead of claiming universal parent
forgery rejection. Full15/591/372/23 and independent final bytes agree.
Emptyrecordnative pushedb2a214c62dacec87fc063ed2108b2296acb4caad;
remote/protected verified. Root appendV2 private015da375709ffad26bf5f8cb76d50b1b65e9c654f18b7c21be9a47f46182e812
has2nativeprobes629/401/25 and is independently reviewed/tested in progress.
Assignment8068ca54 private tests in progress after4nativeprobes162/90/7.
Root destructor private law predicts90/46null or133/74ordinarypath2; probes
pending. NormalAddMove/AddCharge and gameplay remain open.


The [empty-path record-copy native proof](native_movement_effect_record_empty_copy_conformance.md)
is sealed with source/CLI/receipt review GO and81 independent checks validated.
Initial fullsuite80PASS/1FAIL234.12s: fixture source negative overwrote an already
zero byte. Test changed to XOR its actualbyte; all8 affected checksPASS0.83s,
production/receipt unchanged. All12 independent actual machine workers, full48
observation digest, all58controls and exact3CLI commands passed. Seal e7a534fde897fc1e7520c1de8e8d7f9bb2a7fad6a33520c3fc70f396fe8c024d,
raw f4ac5009002ffcbf107b50fc4b92958b92d6b4918852bff2ebb068dd504706dc,
79638B4pins386loaded1226B261exec23616instructions15120events1008boundaries,
noalloc/free/API/wide/opaque/accounting. Generalclone checkpoint pushedaca442fb.
Assignment4actualnative probes match162/90/7; independentpuretests private.
Recordcopy2V2 fixes returninsideO16/D16 and typedchildmetadata, sourceGO/tests
pending. Root private append2 model matches2native probes629/401/25/oneallocation
with vectorend increment and callerword mutation; independent closure pending.
Next: recordcopy2 pure, assignmentpure, append2, destructor then normalAddMove.


The [general actual-page clone2 law](native_movement_path_clone2_semantics.md)
is independently reviewed GO and passes359 pure tests without skips in13.89s.
It preserves the finite native receipt while admitting actual record-local
headers, arbitrary unread source capacity and broader stack geometry. All15
fields, seven boundaries, imported state and complete7/10 child packets are
checked independently. Empty-record native V3 passes full48cases/58controls;
canonical `e7a534fde897fc1e7520c1de8e8d7f9bb2a7fad6a33520c3fc70f396fe8c024d`,
23616instructions/15120events/1008boundaries, independent native tests pending.
Outer defined flags corrected46 to44 under8D5; scope prose corrected for the
publication guard. Assignment0C5BB0 pure freeze8068ca547b33e765ff9af138c1e5d41842492ff08e5e45d02340650ef7796027
awaits root probes; recordcopy2 independent review/tests now private in progress.


The public [empty-path record-copy model](native_movement_effect_record_empty_copy_semantics.md)
passes345 independent tests without skips in14.92seconds, source review GO.
Root source/native probes match492/315/all20helperstates, with183 destination
bytes written/125 preserved and all308source bytes preserved. Native harness
privatefreeze05c32942f1d5ec95b8884334426f6fcd894f5aa86fa45a45206a0d2c52c840b6
is under `movement_record_copy_empty_native_draft/`, awaiting root gates and
independent tests. General count2 actual-page clone model matches all48 old
whole15field packets and four new actualnative cases across low/signed/top
stack frames and arbitrary in-domain allocated pointers; its independent
tests are private in progress. Root two-entry record-copy draft under
`movement_record_copy2_draft/` also matches two native probes591instructions/
372events/23boundaries/one supplied allocation; it is not independently closed.
Simd_class_review_oct2 authors the empty-destination two-entry path assignment
law0C5BB0, predicted162instructions90events; append/destruction/normalAddMove
and gameplay remain open. Latest native clone checkpoint pushed5689969e,
remote synchronized and all13 protected hashes unchanged.

The public [clone2 native proof](native_movement_path_clone2_conformance.md)
passes123 independent tests without skips in651.26seconds. Canonical seal
`1cddf384c45fb50a60752656acd2560a7e243dd20f0d68b8a963a4a7bb3a739b`:
48cases/59controls/6528instructions/3984events/48 supplied allocations/768
copied bytes, no frees/wide accesses/opaque sites/accounting promotions.
Root actual record-copy probes at alignment0/15 match492instructions315events,
all20helperboundaries/GPR/XMM/fullpages/source308preserve against frozen
model65a1328db50bed2015854a56a169ab83fa43a22dd05a8a5e15e82dec292b191a.
Record-copy pointanchor45e4d085df78b3abdcc5b54404ebc16a36a8fb8ca41ec1c7c0eab9083c3d76df,
386loaded sites/1226bytes; actual8strings +zero path/reserve, no allocation.
Pure independent tests and native harness are private in progress. General
actual-page count2 clone model a3dfd47a6e60d398ea954fa6f8bfa42075c8cbb5fc25e64cfbc82903d772f8d3
awaits independent tests; arbitrary source capacity is unread and preserved.

The public [empty-string native proof](native_movement_empty_string_copy_conformance.md)
passes72 independent tests without skips in56.71seconds, with independent
source/CLI/receipt GO. Seal `c3d9d8598d7aa922157397a27a58aeabf86732e9bb620625d602481dd90c18b1`
binds96 cases/26controls/3168instructions/1632events. Source-only wording V2
replaced slash-separated prose rejected by publication guard; no semantic
change. Root is running the clone2 independent suite serially and drafting
actual-page empty-path record copy15B9B0 (eight empty helpers plus zero-count
09A8E0/9AC40 with no allocation). Fifth_model_oct2 independently reviews it;
simd_class_review_oct2 authors a general actual-page count2 clone model to
permit real caller composition. No native ownership or gameplay promotion.

The public actual-page scalar clone law now passes353 independent tests with
source review GO. Its V2 domain requires conservative stack end and a positive
installed endpoint outside the scalar body and touched data, while permitting
the actual parent continuation0049A921. A test assertion was corrected for
adjacent source/destination spans; full packets already matched. Root clone2
private gates pass48 pure recipes, nine native smokes/all59 controls and the
full48 build, canonical `1cddf384c45fb50a60752656acd2560a7e243dd20f0d68b8a963a4a7bb3a739b`.
Counts:6528instructions/3984events/48 supplied allocations/768 copied bytes.
Independent native tests are pending; no native ownership/gameplay promotion.

Latest copy checkpoint: the public empty80D0 actual-page law and independent
tests pass **364 tests**, no skips, source review GO. See
[the specification](native_movement_empty_string_copy_semantics.md). Private
native harness is frozen at `954dc415e81e4de9f7caab3d15a5f0f63c85e1873ecf1fca808cea411cf32158`
under `.local_decompile/oct2/movement_empty_string_copy_draft/`. Root checked
96 pure recipes, ten native smokes and all26 controls; independent native
tests are being authored. Those checks are private preliminary evidence,
not a published full-corpus seal. Continuous path-clone2 draft and scalar
law are frozen under `movement_path_clone2_draft/` for independent review.
No active native process remains after these probes.

Exact PE `B:\SteamLibrary\steamapps\common\Into the Breach\Breach.exe` has SHA
`31fe352655982398fb3ee8b0bbe80efd5d65e3a9aa11e3dc39d0364354493fe9`.
Python3.13, private Capstone5.0.7/Unicorn2.1.4:

```powershell
$env:PYTHONPATH='.local_decompile/fill_runtime;.'
$env:ITB_EXACT_EXE='B:\SteamLibrary\steamapps\common\Into the Breach\Breach.exe'
```

Run native/tools/tests serially in isolated subprocesses. Remove
`PYTHONFAULTHANDLER` from child environments; even the string`0` enables it
and floods stderr with handled Windows Unicorn exceptions. Pytest root uses
`-p no:faulthandler`. Publish only normalized witnesses, synthetic facts and
digests; executable bytes/raw analysis remain private. Receipt creation is
exclusive and deterministic UTF-8 LF.

The13 protected hashes remain listed in
`.local_decompile/sep30/protected_work.json`, checked by
`.local_decompile/oct1/check_protected.py`. Preserve every unrelated dirty
file and stage only the explicit decompilation tranche. No live game actions.
