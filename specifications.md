# PhysicsActivity

## Descripción

Proyecto para generar informes de actividad laboral

## Objetivo

Procesar archivos Excel con registros de reparto de tratamientos para contabilizar cuántos tratamientos realiza cada físico, teniendo además en cuenta el tiempo activo en el Hospital (reducciones de jornada, vacaciones, días libres). La salida es un dataframe pandas con la serie temporal día a día de cómo avanza el reparto. Se generarán informes que partan de los dataframe que muestres mediante gráficos los datos relevantes.

## Infraestructura

- Datos brutos: Excel
- Procesado de datos: python
- Generación del informe: quarto
- Automatización: github actions

## Descripción de los datos brutos

### Reparto de dosimetrías

Una dosimetría es la unidad básica de cuenta de actividad laboral en el Servicio de Radiofísica. La actividad final se contabiliza contando el número de dosimetrías realizadas considerando además su complejidad. Se ha establecia una clasificación de complejidad por su tipo/localización.

Las dosimetrías realizadas se registran en un Excel denominado RepartoDosimetrias.xls. El archivo consta de una serie de columnas en las que están especificadas los tipos de dosimetrías. En la primera columna está indicada la fecha en la que se ha asignado la dosimetría. La fecha no se anota en todos los registros, pero los registros sin fecha corresponden a la fecha indicada en el registro inmediatamente superior que tenga fecha. Es decir, los registros se generan consecutivamente en dirección inferior, pero solo se anota la fecha en el primer registro realizado ese día. 

Un registro de asignación consiste en indicar el nombre del físico en una fecha dada en el tipo de dosimetría que corresponda. En cada registro puede haber anotaciones correspondientes a distintos físicos si son de distintos tipos de dosimetría.

Alrededor de la tabla principal de asignación el archivo Excel tiene otras celdas con totales rudimentarios para tener información directa en el Excel. La localización de la tabla principal para la extracción de datos es sencilla ignorando las primeras filas en el archivo. El número de filas (skip_rows) es conocido de antemano y se puede dejar como un parámetro de configuración. Está relacionado con el número de físicos de los que se registran datos. Es relativamente robusto en tanto que no se modifique el diseño del informe.

### Disponibilidad laboral

La disponibilidad de los físicos para trabajar haciendo dosimetrías está registrada en el archivo PhysicistAvailability.xlsx. 

El concepto de disponibilidad tiene en cuenta cuántas horas de trabajo aporta cada físico. El número de horas depende de la situación de reducción de jornada en su caso y de las jornadas de trabajo: días laborables de la semana menos los días de vacaciones y ausencias del Servicio por la razón que sea (vacaciones, días de libre disposición, rotaciones externas, bajas...)

La estructura del archivo PhysicistAvailability.xlsx es una tabla con tres columnas (physicist, date, availability). Cada registro contiene un código de físico, la fecha en la que la disponibilidad cambia de valor y la disponibilidad del físico a partir de esa fecha. La disponibilidad puede valer 1 para una dedicación total, un número menor que 1 mayor que 0 si hay una disponibilidad parcial, por una reducción de jornada o una dedicación parcial por tener asignadas otras tareas, cero en el caso de no estar temporalmente en el Servicio, por baja, rotación externa, días libres o de asuntos propios, vacaciones.

## Procesamiento de datos

El procesamiento de datos consiste en generar un dataframe pandas con la serie temporal día a día de cómo avanza el reparto. Para ello, se debe procesar el archivo RepartoDosimetrias.xls para contabilizar cuántos tratamientos realiza cada físico cada día, teniendo además en cuenta el tiempo activo en el Hospital (reducciones de jornada, vacaciones, días libres) registrado en el archivo PhysicistAvailability.xlsx.

La salida del procesamiento de datos es un dataframe pandas con la serie temporal día a día de cómo avanza el reparto. El dataframe tiene una fila por cada día y una columna por cada físico, con el número de dosimetrías realizadas teniendo en cuenta la complejidad y acumuladas desde el principio de año hasta el día considerado. Además el dataframe tiene un grupo adicional de columnas para cada físico, nombradas con el prefijo av_ antepuesto al nombre del físico, en las que se almacena la disponibilidad acumulada del físico desde el principio de año hasta el día considerado. Por último, el dataframe tiene otro grupo adicional de columnas para cada físico, nombradas con el prefijo nac_ antepuesto al nombre del físico, con la división para cada fecha del valor de dosimetrías acumuladas por la disponibilidad acumuladas para cada físico y fecha.

## Generación del informe

El informe se tiene que generar a partir del dataframe generado en el paso anterior. 

El informe se generará mediante quarto y su salida será en html.

Se tiene que generar un gráfico con la evolución temporal de la ratio entre dosimetrías acumuladas y disponibilidad acumulada para cada físico.
