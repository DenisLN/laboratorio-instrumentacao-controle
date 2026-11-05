# Resumo da sessão de bancada: Experimento 10 (compensador avanço de fase)

Sessão de 29/10/2026 (dados em `sessoes/sessao_2026-10-29_19-21-57`). Tabelas 1 a 4 medidas; faltam as 5, 6 e 7 (circuito RLC).

## 1. Montagem do ambiente

- **Osciloscópio 1 (Agilent DSO-X 2002A, `MY51452608`).** A CLI só procura Tektronix, então foi preciso passar o recurso:
  `conectar USB0::0x0957::0x179B::MY51452608::0::INSTR`. Os outros recursos Agilent (`MY51452601`, `MY59240844`) e os dois Tek da USB davam `VI_ERROR_NCIC`.
- **Mudança de lab.** No segundo lab o osciloscópio era um **Tektronix TBS 1052B** (`C041356`); o `conectar` simples funcionou. O Agilent passou a dar `VI_ERROR_NCIC` (USB travada).
- **Gerador:** Tektronix AFG1022. **Fonte:** Formis FOR-5005, ±12 V (12,1 V e 12,2 V). Amp-op: TL074 (no lugar do LM324).
- **Mudança no código:** `labscope/sessao/cli.py` ganhou a opção `--fila ARQUIVO`. A sessão interativa também lê comandos de um arquivo acompanhado (`fila_cli.txt` na raiz), o que permitiu digitar na sessão sem tocar no teclado. Não foi commitada. `fila_cli.txt` aparece no git e pode ir para o `.gitignore`.
- **Manter acordado:** pedido via `request_keep_awake` (session_idle) e um script PowerShell (`SetThreadExecutionState`) na aba "Manter acordado". Ele está no scratchpad, não no projeto.

## 2. Resultados por tabela (capturas mantidas)

| Tabela | Caso | Captura | Resultado |
|---|---|---|---|
| 1 | 500 Hz (inversor) | #02 | 4 de 4 OK |
| 2 | 20 Hz | #20 | \|G\| 0,295 (teoria 0,299), fase 48,3° (49,3°) |
| 2 | 100 Hz | #21 | \|G\| 1,051 (1,073), fase 53,5° (50,3°) |
| 2 | 300 Hz | #19 | \|G\| 1,976 (1,768, +11,7 %), fase 31,2° (25,4°) |
| 2 | 1 kHz | #22 | \|G\| 2,388 (1,975, +20,9 %), fase 9,0° (8,3°) |
| 2 | 3 kHz | #23 | \|G\| 2,283 (1,997, +14,3 %), fase −2,7° (2,8°) |
| 2 | 5 kHz | #24 | \|G\| 2,179 (1,999, +9,0 %), fase −8,0° (1,7°) |
| 3 | RC, degrau | #40 | 5 de 7 OK; Ts 0,11 ms (0,09), Vc 0,479 V (0,481); τ e Tr acima (média móvel de 5,7 µs) |
| 4 | RC, 100 Hz | #41 | 4 de 4 OK |

Observações:
- **Tabela 2 foi medida em 1 Vpp**, não nos 2 Vpp da folha (a 2 Vpp, em 300 Hz, a saída cortava em ±2,2 V, o que é ±11 V no amp-op antes do inversor R3/R4, limite normal do TL074 com ±12 V). A coluna "Vpp saída" fica pela metade da teoria. \|G\| e fase valem.
- **Ganho de alta frequência 10 a 20 % acima da teoria** (300 Hz a 5 kHz): provável tolerância de C1 e C2. Não medido.
- As 24 capturas inúteis foram descartadas com `descartar n` (pastas renomeadas com `_descartada`, nada apagado).

## 3. O que estava errado (cronologia dos problemas)

1. **Gerador em quadrada** nas capturas #08 a #12 da Tabela 2 (CH1 com 100 % das amostras nos extremos). A análise ajustava uma senoide à fundamental da quadrada e dava resultados falsos.
2. **C2 errado** na Tabela 2 (apareceu um valor perto de 10 nF no lugar de 100 nF). Ganho e fase passavam muito da teoria em 100 e 300 Hz; depois da correção as duas ficaram dentro de cerca de 10 %.
3. **R1 = 1,5 kΩ em vez de 15 kΩ** na Tabela 3, mais uma **ligação errada** no circuito (identificada pelo usuário). Com isso o ganho de regime ia a 1,14 e a resposta era lenta (τ de 0,5 a 1 ms em vez de 20 µs). Depois de corrigir a ligação, a captura #39/#40 fechou.
4. **Cc eletrolítico de 1 µF** foi suspeito (polaridade com tensão invertida). Foi trocado por dois de 4,7 µF em série (2,35 µF, informado à CLI com `set Cc 2.35u`), e depois voltou para 1 µF (`set Cc 1u`). O tempo de resposta acompanhou o Cc (τ ×2,34 para Cc ×2,35).
5. **Oscilação de uns 46 kHz** na saída do somador (#37, ±2,4 V), vista só com a ligação errada. Provavelmente consequência dela, ou da ponta de 1× carregando o nó. Não foi confirmado.

## 4. Erros meus que foram corrigidos durante a sessão

- Disse que a saturação do amp-op em ±2,2 V explicava a Tabela 3. A simulação mostrou que um limite de ±11 V só estica o Tr de 0,05 para 0,08 ms; a causa era a ligação.
- Disse que o circuito seguia a teoria em 40 mVpp. O ajuste olhava uma janela de 8 ms com ruído e não via a subida de 0,3 ms.
- Atribuí o desvio à "cauda lenta" do cancelamento zero-polo. A conta deu resíduo de 0,7 %, então não era isso.
- Pensei que o corte da Tabela 2 fosse a escala vertical do osciloscópio. O usuário disse que 1 V/div também cortava, e era saturação do circuito.

## 5. Pendências

- **Tabelas 5, 6 e 7** (RLC): trocar o circuito (L1 = 77 mH) e medir o degrau (Tabela 5, com ζ, ωn e ωd na 6) e a senoide de 100 Hz (Tabela 7).
- **Tabela 2 em 2 Vpp**, se o professor exigir. Os casos de 20 e 100 Hz dá para refazer; de 300 Hz em diante, verificar se a saída ainda corta agora que a ligação foi corrigida.
- **Tabela 3:** τ e Tr ainda saem acima (+197 % e +44 %) por resolução (média móvel de 5,7 µs contra τ de 20 µs). O Ts passa (+31 %).
- Decidir sobre `fila_cli.txt` (`.gitignore`) e sobre commitar a opção `--fila`.

## 6. Comandos úteis da CLI usados

```
python -m labscope --exp 10 --fila fila_cli.txt     # sessão com fila de comandos
conectar [recurso|sim|pasta]    caso 2.1 / 3.1 / 4.1    preparar    adquirir
set Cc 1u     comp     tabela 2|3|4     descartar n     scpi <comando>
```

Ajustes de escala no Tektronix por SCPI: `CH1:SCALE`, `CH2:SCALE`, `CH2:POSITION`, `HOR:SCALE`, `TRIG:MAIN:LEVEL`.
No Agilent: `:CHAN1:SCAL`, `:TIM:SCAL`.
