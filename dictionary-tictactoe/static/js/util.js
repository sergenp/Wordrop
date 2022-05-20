function listToMatrix(list, elementsPerSubArray) {
    var matrix = [], i, k;

    for (i = 0, k = -1; i < list.length; i++) {
        if (i % elementsPerSubArray === 0) {
            k++;
            matrix[k] = [];
        }

        matrix[k].push(list[i]);
    }

    return matrix;
}

function createTable(tableId, row_count, column_count) {
    var html = ""
    for (var i = 0; i < row_count; i++) {
        html += "<tr>"
        for (var j = 0; j < column_count; j++) {
            html += '<td></td>'
        }
        html += "</tr>"
    }
    document.getElementById(tableId).innerHTML += html;
}