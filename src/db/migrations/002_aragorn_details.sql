-- Assegna a schede esistenti senza dati di gioco un livello/classe di default.
-- Aragorn (personaggio già presente) diventa Livello 1, Classe Guerriero.
UPDATE sheets
SET data = '{"level":1,"class":"warrior"}'
WHERE kind = 'character'
  AND name = 'Aragorn'
  AND (data = '{}' OR data IS NULL OR data = '');
