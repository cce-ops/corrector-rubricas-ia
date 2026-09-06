import streamlit as st
from google import genai
import pypdf
import time
from pptx import Presentation  # Para leer PowerPoints
import docx  # Para leer Words

st.title("Corrector Automático por Rúbricas")
st.write("Herramienta de apoyo para la evaluación de proyectos de ingeniería.")

# Caja para la contraseña de la IA
api_key = st.text_input("Introduce tu API Key de Gemini:", type="password")

# SÚPER FUNCIÓN: Lee PDF, PPTX y DOCX
def extraer_texto_archivo(archivo):
    texto = ""
    nombre = archivo.name.lower()
    
    try:
        if nombre.endswith('.pdf'):
            lector = pypdf.PdfReader(archivo)
            for pagina in lector.pages:
                texto += pagina.extract_text() + "\n"
                
        elif nombre.endswith('.pptx'):
            presentacion = Presentation(archivo)
            for diapositiva in presentacion.slides:
                for forma in diapositiva.shapes:
                    if hasattr(forma, "text"):
                        texto += forma.text + "\n"
                        
        elif nombre.endswith('.docx'):
            documento = docx.Document(archivo)
            for parrafo in documento.paragraphs:
                texto += parrafo.text + "\n"
    except Exception as e:
        texto += f"[Error al extraer texto de este archivo: {e}]\n"
        
    return texto

col1, col2 = st.columns(2)

with col1:
    st.subheader("1. Rúbrica")
    opcion_rubrica = st.radio("¿Cómo vas a introducir la rúbrica?", ["Pegar texto", "Subir PDF"])
    
    rubrica_texto = ""
    archivo_rubrica = None
    
    if opcion_rubrica == "Pegar texto":
        rubrica_texto = st.text_area("Pega aquí los criterios:", height=200)
    else:
        # La rúbrica suele ser un solo PDF
        archivo_rubrica = st.file_uploader("Sube la rúbrica en PDF", type=["pdf"], key="rubrica_pdf")

with col2:
    st.subheader("2. Trabajo del Alumno")
    # AHORA ACEPTA MULTIPLES ARCHIVOS Y FORMATOS
    archivos_alumno = st.file_uploader(
        "Sube los archivos (PDF, Word, PowerPoint)", 
        type=["pdf", "docx", "pptx"], 
        accept_multiple_files=True, # <--- LA MAGIA ESTÁ AQUÍ
        key="alumno_archivos"
    )

if st.button("Evaluar Trabajo", type="primary"):
    if not api_key:
        st.error("Por favor, introduce tu API Key arriba para conectar con la IA.")
    elif opcion_rubrica == "Pegar texto" and not rubrica_texto:
        st.warning("Por favor, pega el texto de la rúbrica.")
    elif opcion_rubrica == "Subir PDF" and not archivo_rubrica:
        st.warning("Por favor, sube el archivo PDF de la rúbrica.")
    elif not archivos_alumno: # Si la lista está vacía
        st.warning("Por favor, sube al menos un archivo del alumno.")
    else:
        st.info("Procesando archivos y analizando... (esto puede tardar unos segundos)")
        
        try:
            # Extraemos rúbrica
            if opcion_rubrica == "Subir PDF":
                texto_rubrica_final = extraer_texto_archivo(archivo_rubrica)
            else:
                texto_rubrica_final = rubrica_texto
                
            # UNIMOS EL TEXTO DE TODOS LOS ARCHIVOS DEL ALUMNO
            texto_alumno_final = ""
            for archivo in archivos_alumno:
                texto_alumno_final += f"\n\n--- INICIO DEL ARCHIVO: {archivo.name} ---\n"
                texto_alumno_final += extraer_texto_archivo(archivo)
                texto_alumno_final += f"\n--- FIN DEL ARCHIVO: {archivo.name} ---\n"
            
            client = genai.Client(api_key=api_key)
            
            instrucciones = f"""
            Eres un profesor de ingeniería muy estricto. Tu tarea es evaluar el trabajo de un alumno que puede estar compuesto por varios archivos.
            
            REGLAS OBLIGATORIAS:
            - Debes usar EXCLUSIVAMENTE la rúbrica proporcionada.
            - Debes evaluar TODOS Y CADA UNO de los criterios que aparezcan en la rúbrica. No puedes omitir ninguno.
            - Si el alumno no menciona nada sobre un criterio en ninguno de sus archivos, su nota en ese criterio es 0.
            
            RÚBRICA:
            {texto_rubrica_final}
            
            TRABAJO DEL ALUMNO (Extraído de sus archivos):
            {texto_alumno_final}
            
            ESTRUCTURA DE TU RESPUESTA:
            1. NOTA FINAL CALCULADA: (Suma de puntos obtenidos / Suma de puntos máximos posibles de la rúbrica).
            2. DESGLOSE POR CRITERIO (Obligatorio evaluar cada uno): 
            - Nombre del Criterio: [Puntos asignados] / [Máximo posible]
            - Justificación DETALLADA: Cita qué ha hecho bien el alumno y qué elementos técnicos le han faltado explícitamente según la rúbrica.
            """
            
            intentos_maximos = 3
            for intento in range(intentos_maximos):
                try:
                    response = client.models.generate_content(
                        model='gemini-3.6-flash',
                        contents=instrucciones
                    )
                    st.success("¡Evaluación completada!")
                    st.write(response.text)
                    break 
                    
                except Exception as error_ia:
                    if "503" in str(error_ia) and intento < (intentos_maximos - 1):
                        st.warning(f"Servidores de Google muy ocupados. Reintentando en 5 segundos... (Intento {intento + 1} de {intentos_maximos})")
                        time.sleep(5)
                    else:
                        raise error_ia 
            
        except Exception as e:
            st.error(f"Hubo un error al procesar el archivo o conectar con la IA: {e}")
