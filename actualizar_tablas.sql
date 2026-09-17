ALTER TABLE public.movimientos_bancarios 
ADD COLUMN IF NOT EXISTS archivo_origen text DEFAULT 'Desconocido',
ADD COLUMN IF NOT EXISTS usuario_carga text DEFAULT 'Sistema';
