package com.poo.siga.dto.nota;

import com.poo.siga.model.Nota;
import java.time.LocalDateTime;

public record NotaResponse(
    Integer id, Integer turmaId, Integer disciplinaId,
    Integer alunoId, Integer periodo, String tipoAvaliacao, 
    Double valor, LocalDateTime dataLancamento, String usuarioLancamento
) {
    public static NotaResponse from(Nota n) {
        return new NotaResponse(
            n.getId(), n.getTurma().getId(), n.getDisciplina().getId(), n.getAluno().getId(),
            n.getPeriodo(), n.getTipoAvaliacao().name(), n.getValor(), n.getDataLancamento(),n.getUsuarioLancamento()
        );
    }
}
